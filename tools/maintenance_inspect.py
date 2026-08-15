#!/usr/bin/env python3
"""Read-only global operational sensor for the future MobiliPresenter supervisor."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import agent, capability_gates, continuation, coordination
from tools.coordination_remote import CoordinationRemoteError, GhApiTransport, GitHubCoordinationAuthority
ERROR_EXIT=2
ACTIONS=("CONTINUE","RECONCILE","HANDOFF","PAUSE","NEEDS_HUMAN")
ACTION_PRIORITY={"CONTINUE":0,"HANDOFF":1,"PAUSE":2,"RECONCILE":3,"NEEDS_HUMAN":4}

def capability_snapshot():
    out=[]
    for value in capability_gates.discover_capabilities():
        p=capability_gates.build_review_plan(value)
        out.append({"id":value["id"],"policy":value["policy"],"supervisorParticipation":capability_gates.supervisor_participation(value),"reviewAction":p["action"],"nextGates":p["nextGates"],"backlogCount":len(p["backlog"]),"roundsWithoutActiveGates":p["roundsWithoutActiveGates"],"maxRoundsWithoutActiveGates":p["maxRoundsWithoutActiveGates"],"deferReason":p["deferReason"],"reviewPlanHash":p["planHash"]})
    return out

def continuation_snapshot():
    return [{"id":v["id"],"actor":v["actor"],"status":v["status"],"branch":v["branch"],"prNumber":v["prNumber"],"completed":v["completed"],"remaining":v["remaining"],"nextAction":v["nextAction"],"lastKnownGood":v["lastKnownGood"],"blockedBy":v["blockedBy"],"handoffTo":v["handoffTo"],"stateHash":continuation.state_hash(v)} for v in continuation.discover()]

def _pr_class(state,head_ref):
    if head_ref==state["git"].get("activeDevelopmentBranch"): return "active-development"
    if isinstance(head_ref,str) and head_ref in set(state["git"].get("preserveBranches") or []): return "preserved"
    if isinstance(head_ref,str) and head_ref.startswith("ops/git-ops-"): return "operations"
    return "unclassified"

def observe_open_prs(state):
    repo=state["project"]["repository"]; ok,payload=agent.run_gh_json(f"repos/{repo}/pulls?state=open&per_page=100")
    if not ok or not isinstance(payload,list): return {"available":False,"reason":"OPEN_PR_READ_FAILED","detail":payload,"items":[]}
    items=[]
    for raw in payload:
        if not isinstance(raw,dict): continue
        head=raw.get("head") if isinstance(raw.get("head"),dict) else {}; base=raw.get("base") if isinstance(raw.get("base"),dict) else {}; head_sha=head.get("sha"); runs=[]; ci="unknown"
        if isinstance(head_sha,str):
            rok,rp=agent.run_gh_json(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
            if rok and isinstance(rp,dict) and isinstance(rp.get("workflow_runs"),list):
                runs=[{"name":x.get("name"),"status":x.get("status"),"conclusion":x.get("conclusion"),"id":x.get("id")} for x in rp["workflow_runs"] if isinstance(x,dict)]; ci=agent.aggregate_ci(runs)
        href=head.get("ref"); items.append({"number":raw.get("number"),"draft":raw.get("draft"),"headRef":href,"headSha":head_sha,"baseRef":base.get("ref"),"classification":_pr_class(state,href),"ci":ci,"workflows":runs})
    items.sort(key=lambda x:int(x.get("number") or 0)); return {"available":True,"items":items}
def observe_coordination():
    try:
        authority=GitHubCoordinationAuthority(GhApiTransport()); observed=authority.observe(); current=coordination.compact_expired(observed.state,observed.authority_now)
        return {"available":True,"authorityBranch":authority.authority_branch,"authorityHead":observed.head_sha,"intents":current["intents"],"leases":current["leases"]}
    except (CoordinationRemoteError,OSError) as exc:
        return {"available":False,"reason":getattr(exc,"code","COORDINATION_UNAVAILABLE"),"detail":getattr(exc,"detail",str(exc)),"intents":[],"leases":[]}
def finding(action,code,detail,subject=None):
    if action not in ACTIONS: raise RuntimeError("MAINTENANCE_ACTION_INVALID")
    v={"action":action,"code":code,"detail":detail}
    if subject is not None: v["subject"]=subject
    return v

def decide(state,verification,capabilities,*,remote_requested,pull_requests,coordination_state,continuations=None):
    fs=[]; continuations=continuations or []
    if not verification.get("ok"):
        failed=[x.get("name") for x in verification.get("checks",[]) if x.get("status")=="FAIL"]; fs.append(finding("RECONCILE","VERIFICATION_FAILED",f"failed checks: {', '.join(str(x) for x in failed)}","repository"))
    blockers=state["development"].get("blockers") or []
    if blockers: fs.append(finding("PAUSE","EXPLICIT_BLOCKERS","; ".join(str(x) for x in blockers),"development"))
    for task in continuations:
        subject=f"continuation:{task['id']}"; status=task["status"]
        if status=="HANDOFF": fs.append(finding("HANDOFF","CONTINUATION_HANDOFF_REQUIRED",f"handoff to {task['handoffTo']}: {task['nextAction']}",subject))
        elif status=="WAITING": fs.append(finding("PAUSE","CONTINUATION_WAITING","; ".join(task["blockedBy"]),subject))
        elif status in {"READY","IN_PROGRESS"}: fs.append(finding("CONTINUE","CONTINUATION_RUNNABLE",task["nextAction"] or "finish and mark done",subject))
    for item in capabilities:
        if item["policy"]!="experimental": continue
        if item.get("supervisorParticipation","active")=="isolated": continue
        if item["reviewAction"]=="REVIEW_EMPTY_LIMIT": fs.append(finding("NEEDS_HUMAN","CAPABILITY_EMPTY_LIMIT","formal capability review reached its configured empty-round limit",item["id"]))
        elif item["reviewAction"]=="TEST_NEXT_GATES": fs.append(finding("CONTINUE","CAPABILITY_GATES_DUE",f"next Gates: {', '.join(item['nextGates'])}",item["id"]))
        elif item["reviewAction"]=="REVIEW_EMPTY_ROUND": fs.append(finding("CONTINUE","CAPABILITY_EMPTY_REVIEW_DUE","re-evaluate the recorded deferral reason",item["id"]))
    if remote_requested:
        if not pull_requests.get("available"): fs.append(finding("NEEDS_HUMAN","REMOTE_PR_INVENTORY_UNAVAILABLE",str(pull_requests.get("reason") or "unknown"),"github"))
        else:
            for pr in pull_requests.get("items",[]):
                if pr.get("classification")=="unclassified": fs.append(finding("RECONCILE","UNCLASSIFIED_OPEN_PR",f"open PR #{pr.get('number')} head {pr.get('headRef')} is not mapped to active/preserved/operations state",f"pr:{pr.get('number')}"))
            active_pr=state["development"].get("prNumber")
            if isinstance(active_pr,int):
                matches=[x for x in pull_requests.get("items",[]) if x.get("number")==active_pr]
                if not matches: fs.append(finding("RECONCILE","ACTIVE_PR_NOT_OPEN",f"ProjectState references PR #{active_pr}, but it is not open","development"))
                else:
                    ci=matches[0].get("ci")
                    if ci=="failed": fs.append(finding("RECONCILE","ACTIVE_PR_CI_FAILED",f"PR #{active_pr} CI is failed",f"pr:{active_pr}"))
                    elif ci=="pending": fs.append(finding("PAUSE","ACTIVE_PR_CI_PENDING",f"PR #{active_pr} CI is pending",f"pr:{active_pr}"))
                    elif ci=="unknown": fs.append(finding("NEEDS_HUMAN","ACTIVE_PR_CI_UNKNOWN",f"PR #{active_pr} CI could not be established",f"pr:{active_pr}"))
        canonical=any(x["id"]=="coordination-leases" and x["policy"]=="canonical" for x in capabilities)
        if canonical and not coordination_state.get("available"): fs.append(finding("NEEDS_HUMAN","COORDINATION_AUTHORITY_UNAVAILABLE",str(coordination_state.get("reason") or "unknown"),"coordination-leases"))
        elif coordination_state.get("available") and pull_requests.get("available"):
            open_numbers={x.get("number") for x in pull_requests.get("items",[]) if isinstance(x.get("number"),int)}
            for lease in coordination_state.get("leases",[]):
                owner=lease.get("owner") if isinstance(lease,dict) and isinstance(lease.get("owner"),dict) else {}; owner_pr=owner.get("pr")
                if isinstance(owner_pr,int) and owner_pr not in open_numbers: fs.append(finding("RECONCILE","LEASE_OWNER_PR_NOT_OPEN",f"lease {lease.get('leaseId')} references non-open PR #{owner_pr}","coordination-leases"))
    if not fs: fs.append(finding("CONTINUE","NEXT_TRANSITION_AVAILABLE",state["development"]["nextTransition"],"development"))
    indexed=list(enumerate(fs)); _,best=max(indexed,key=lambda pair:(ACTION_PRIORITY[pair[1]["action"]],-pair[0]))
    rec={"action":best["action"],"reasonCode":best["code"],"focus":best.get("subject"),"detail":best["detail"],"decisionScope":"operational-only","semanticAuthority":False,"allowedActions":list(ACTIONS)}
    return fs,rec
def build_inspection(state,verification,observed_git,capabilities,*,remote_requested,pull_requests,coordination_state,continuations=None):
    continuations=continuations or []; fs,rec=decide(state,verification,capabilities,remote_requested=remote_requested,pull_requests=pull_requests,coordination_state=coordination_state,continuations=continuations)
    body={"schemaVersion":"MaintenanceInspection 0.2","repository":state["project"]["repository"],"projectState":{"phase":state["development"]["phase"],"checkpoint":state["development"]["checkpoint"],"nextTransition":state["development"]["nextTransition"],"activeDevelopmentBranch":state["git"].get("activeDevelopmentBranch"),"developmentPrNumber":state["development"].get("prNumber"),"blockers":state["development"].get("blockers") or []},"verification":verification,"observedGit":observed_git,"capabilities":capabilities,"continuations":continuations,"remoteRequested":remote_requested,"pullRequests":pull_requests,"coordination":coordination_state,"findings":fs,"recommendation":rec,"readOnly":True}
    return {**body,"inspectionHash":capability_gates.stable_hash(body)}
def inspect(include_remote):
    state=agent.load_json(agent.STATE_PATH); errors=agent.validate_state_shape(state)
    if errors: raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    verification=agent.verify_state(include_remote=include_remote); observed=agent.observed_git(); caps=capability_snapshot(); cont=continuation_snapshot(); prs=observe_open_prs(state) if include_remote else {"available":False,"reason":"NOT_REQUESTED","items":[]}; coord=observe_coordination() if include_remote else {"available":False,"reason":"NOT_REQUESTED","intents":[],"leases":[]}
    return build_inspection(state,verification,observed,caps,remote_requested=include_remote,pull_requests=prs,coordination_state=coord,continuations=cont)
def main(argv=None):
    p=argparse.ArgumentParser(prog="maintenance-inspect"); p.add_argument("--json",action="store_true",dest="as_json"); p.add_argument("--remote",action="store_true"); args=p.parse_args(argv)
    try:
        payload=inspect(args.remote)
        if args.as_json: print(json.dumps(payload,indent=2,ensure_ascii=False))
        else:
            print("MAINTENANCE INSPECT"); print(f"  recommendation: {payload['recommendation']['action']}"); print(f"  reason: {payload['recommendation']['reasonCode']}"); print(f"  focus: {payload['recommendation'].get('focus') or '(none)'}"); print(f"  continuations: {len(payload['continuations'])}"); print(f"  inspectionHash: {payload['inspectionHash']}")
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}"); return ERROR_EXIT
if __name__=="__main__": raise SystemExit(main())
