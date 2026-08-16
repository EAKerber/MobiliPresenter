#!/usr/bin/env python3
"""Read-only integration reconciliation planner for MobiliPresenter."""
from __future__ import annotations
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from typing import Any,Iterable
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
STATE_PATH=ROOT/"ops"/"state"/"project.json";ERROR_EXIT=2;SCHEMA_VERSION="IntegrationReconcilePlan 0.1"
SHARED=("viewer-next/src/api/","viewer-next/src/bootstrap.ts","viewer-next/index.html","viewer-next/package.json","viewer-next/tsconfig.json",".github/workflows/",)
from tools.canonical import stable_hash
from tools.semantics.branches import parse_branch_name

def _branch_domain(head_ref):
    try:identity=parse_branch_name(head_ref)
    except RuntimeError:return None
    if identity.get("grammar")=="canonical" and identity.get("declaredClass") not in {"work","experiment"}:return None
    return identity.get("semanticDomain")
def classify_path(path):
    prefixes=(("viewer-next/src/api/","viewer-api"),("viewer-next/src/ui/","viewer-ui"),("viewer-next/src/presentation/","viewer-presentation"),("viewer-next/src/runtime/","viewer-runtime"),("viewer-next/src/renderer/","viewer-renderer"),("viewer-next/tests/","viewer-tests"),("scene-core/","scene-core"),(".github/workflows/","ci"),("docs/","docs"))
    for prefix,domain in prefixes:
        if path.startswith(prefix):return domain
    if path.startswith(("ops/","tools/")) or path=="AGENTS.md":return "operations"
    return "other"
def is_shared_resource(path):return any(path.startswith(x) if x.endswith("/") else path==x for x in SHARED)
def boundary_assessment(head_ref,changed_files):
    files,violations,reviews=sorted(set(changed_files)),[],[];domain=_branch_domain(head_ref)
    if domain=="engine":
        for path in files:
            if path.startswith("viewer-next/src/ui/"):violations.append({"path":path,"code":"ENGINE_TOUCHED_UI"})
            elif path.startswith(("ops/","tools/")) or path=="AGENTS.md":violations.append({"path":path,"code":"ENGINE_TOUCHED_GITOPS"})
            elif path.startswith("viewer-next/src/api/"):reviews.append({"path":path,"code":"SHARED_API_CONTRACT_REVIEW"})
    elif domain=="ui":
        forbidden=("viewer-next/src/presentation/","viewer-next/src/runtime/","viewer-next/src/renderer/","viewer-next/src/fixtures/","scene-core/")
        for path in files:
            if path.startswith(forbidden):violations.append({"path":path,"code":"UI_TOUCHED_ENGINE_DOMAIN"})
            elif path.startswith("viewer-next/src/api/"):reviews.append({"path":path,"code":"SHARED_API_CONTRACT_REVIEW"})
            elif path.startswith(("ops/","tools/")) or path=="AGENTS.md":violations.append({"path":path,"code":"UI_TOUCHED_GITOPS"})
    elif domain=="operations":
        for path in files:
            if path.startswith(("viewer-next/","scene-core/")):violations.append({"path":path,"code":"GITOPS_TOUCHED_PRODUCT"})
    return {"sharedResourcesTouched":[p for p in files if is_shared_resource(p)],"boundaryReview":reviews,"boundaryViolations":violations}
def aggregate_ci(runs,head_sha,head_ref=""):
    latest={};operations=_branch_domain(head_ref)=="operations"
    for run in runs:
        name=str(run.get("name") or "")
        if not name or (name=="Agent Ops" and not operations):continue
        latest.setdefault(name,run)
    selected=list(latest.values())
    if not selected:status="unknown"
    elif any(str(r.get("status","")).lower()!="completed" for r in selected):status="pending"
    else:
        conclusions={str(r.get("conclusion") or "").lower() for r in selected};status="green" if conclusions<={"success","neutral","skipped"} else ("failed" if conclusions&{"failure","cancelled","timed_out","action_required","startup_failure"} else "unknown")
    return {"status":status,"validatedSha":head_sha,"runs":[{k:r.get(k) for k in ("name","id","status","conclusion")} for r in selected]}
def domain_summary(files):
    out={}
    for path in files:out[classify_path(path)]=out.get(classify_path(path),0)+1
    return dict(sorted(out.items()))
def state_assessment(state,pr):
    git_state,dev=state.get("git",{}),state.get("development",{});active,active_pr=git_state.get("activeDevelopmentBranch"),dev.get("prNumber");alignment="aligned-active-development" if (active,active_pr)==(pr.get("headRef"),pr.get("number")) else ("no-active-development" if active is None and active_pr is None else "development-identity-mismatch");stale=[]
    if pr.get("merged") and active==pr.get("headRef"):stale.append("git.activeDevelopmentBranch")
    if pr.get("merged") and active_pr==pr.get("number"):stale.append("development.prNumber")
    return {"alignment":alignment,"activeDevelopmentBranch":active,"activePrNumber":active_pr,"phase":dev.get("phase"),"checkpoint":dev.get("checkpoint"),"nextTransition":dev.get("nextTransition"),"blockers":dev.get("blockers") or [],"likelyStaleFields":stale,"stateReviewRecommended":bool(pr.get("merged")),"postMergeReviewFields":["git.activeDevelopmentBranch","development.prNumber","development.phase","development.checkpoint","development.nextTransition","development.blockers"]}
def recommendation(obs,boundary,ci):
    pr,target,ancestry=obs["pr"],obs["target"],obs["ancestry"];base_to_target,target_to_head=ancestry["declaredBaseToTarget"],ancestry["targetToHead"]
    if pr.get("merged"):action,reason="already-merged","pull-request-is-already-merged"
    elif pr.get("state")!="open":action,reason="no-action","pull-request-is-not-open"
    elif boundary["boundaryViolations"]:action,reason="semantic-owner-review","cross-boundary-paths-detected"
    elif pr.get("baseRef")!=target.get("branch"):action,reason=(("retarget-to-control-and-revalidate","declared-base-is-contained-in-control") if base_to_target.get("status") in {"ahead","identical"} else ("manual-reconciliation","declared-base-is-not-cleanly-contained-in-control"))
    elif target_to_head.get("status")=="behind":action,reason="no-action","head-is-already-contained-in-control"
    elif ci["status"]=="failed":action,reason="fix-ci-before-integration","head-ci-is-failed"
    elif ci["status"] in {"pending","unknown"}:action,reason="wait-for-ci","head-ci-is-not-proven-green"
    else:action,reason="review-current-target","base-is-control-and-ci-is-green"
    return {"action":action,"reason":reason,"safeToApply":False,"note":"Read-only recommendation. Semantic approval, retargeting and merge remain separate operations."}
def build_plan(obs):
    pr,files=obs["pr"],sorted(set(obs.get("changedFiles") or []));boundary=boundary_assessment(str(pr.get("headRef") or ""),files);ci=aggregate_ci(obs.get("workflowRuns") or [],pr.get("headSha"),str(pr.get("headRef") or ""));body={"schemaVersion":SCHEMA_VERSION,"repository":obs["repository"],"pr":pr,"target":obs["target"],"ancestry":obs["ancestry"],"scope":{"changedFileCount":len(files),"changedFiles":files,"domains":domain_summary(files),**boundary},"ci":ci,"canonicalState":state_assessment(obs["projectState"],pr),"recommendation":recommendation(obs,boundary,ci),"applyEligible":False,"note":"Read-only plan. Any PR head, target head, CI or path drift invalidates this plan."};return {**body,"planHash":stable_hash(body)}
class GhObserver:
    def __init__(self,repository):self.repository=repository
    def _run(self,endpoint):
        if shutil.which("gh") is None:raise RuntimeError("GH_NOT_FOUND")
        proc=subprocess.run(["gh","api",endpoint],cwd=ROOT,text=True,capture_output=True,check=False)
        if proc.returncode:raise RuntimeError(f"GH_API_FAILED:{endpoint}:{(proc.stderr or proc.stdout).strip()}")
        try:return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:raise RuntimeError(f"GH_JSON_INVALID:{endpoint}") from exc
    def _pages(self,endpoint):
        out,page=[],1
        while True:
            payload=self._run(f"{endpoint}{'&' if '?' in endpoint else '?'}per_page=100&page={page}")
            if not isinstance(payload,list):raise RuntimeError(f"GH_PAGE_INVALID:{endpoint}")
            out.extend(payload)
            if len(payload)<100:return out
            page+=1
    @staticmethod
    def _compare(value):
        if not isinstance(value,dict):return {"status":"unknown","aheadBy":None,"behindBy":None,"mergeBaseSha":None}
        merge_base=value.get("merge_base_commit") if isinstance(value.get("merge_base_commit"),dict) else {};return {"status":value.get("status"),"aheadBy":value.get("ahead_by"),"behindBy":value.get("behind_by"),"mergeBaseSha":merge_base.get("sha")}
    def observe(self,pr_number,target_branch,project_state):
        repo,pr=self.repository,self._run(f"repos/{self.repository}/pulls/{pr_number}")
        if not isinstance(pr,dict):raise RuntimeError("PR_READ_INVALID")
        head,base=pr.get("head") or {},pr.get("base") or {};target_commit=self._run(f"repos/{repo}/commits/{quote(target_branch,safe='')}");target_sha,base_sha,head_sha=target_commit.get("sha"),base.get("sha"),head.get("sha")
        if not all(isinstance(x,str) for x in (target_sha,base_sha,head_sha)):raise RuntimeError("PR_IDENTITY_INCOMPLETE")
        workflows=self._run(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
        return {"repository":repo,"pr":{"number":pr.get("number"),"state":pr.get("state"),"draft":pr.get("draft"),"merged":bool(pr.get("merged")),"mergeable":pr.get("mergeable"),"headRef":head.get("ref"),"headSha":head_sha,"baseRef":base.get("ref"),"baseSha":base_sha},"target":{"branch":target_branch,"sha":target_sha},"ancestry":{"declaredBaseToTarget":self._compare(self._run(f"repos/{repo}/compare/{base_sha}...{target_sha}")),"targetToHead":self._compare(self._run(f"repos/{repo}/compare/{target_sha}...{head_sha}"))},"changedFiles":[x.get("filename") for x in self._pages(f"repos/{repo}/pulls/{pr_number}/files") if isinstance(x,dict) and isinstance(x.get("filename"),str)],"workflowRuns":workflows.get("workflow_runs",[]) if isinstance(workflows,dict) else [],"projectState":project_state}
def load_state():
    try:value=json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:raise RuntimeError("STATE_FILE_MISSING") from exc
    except json.JSONDecodeError as exc:raise RuntimeError(f"STATE_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value,dict):raise RuntimeError("STATE_ROOT_INVALID")
    return value
def render_text(plan):
    pr,target,a,scope,rec=plan["pr"],plan["target"],plan["ancestry"],plan["scope"],plan["recommendation"];return "\n".join(("INTEGRATION RECONCILE PLAN",f"  PR: #{pr['number']} {pr['headRef']} @ {pr['headSha']}",f"  declared base: {pr['baseRef']} @ {pr['baseSha']}",f"  target: {target['branch']} @ {target['sha']}",f"  base -> target: {a['declaredBaseToTarget']['status']}",f"  target -> head: {a['targetToHead']['status']}",f"  changed files: {scope['changedFileCount']}",f"  shared resources: {len(scope['sharedResourcesTouched'])}",f"  boundary violations: {len(scope['boundaryViolations'])}",f"  CI: {plan['ci']['status']}",f"  recommendation: {rec['action']} ({rec['reason']})",f"  apply eligible: {plan['applyEligible']}",f"  planHash: {plan['planHash']}"))
def main():
    parser=argparse.ArgumentParser(description="Read-only MobiliPresenter integration reconciliation planner");parser.add_argument("command",choices=("reconcile-plan",));parser.add_argument("pr",type=int);parser.add_argument("--target");parser.add_argument("--json",action="store_true",dest="as_json");args=parser.parse_args()
    try:
        state=load_state();repository=state.get("project",{}).get("repository");target=args.target or state.get("git",{}).get("controlBranch")
        if not isinstance(repository,str) or not repository:raise RuntimeError("REPOSITORY_STATE_INVALID")
        if not isinstance(target,str) or not target:raise RuntimeError("TARGET_BRANCH_INVALID")
        plan=build_plan(GhObserver(repository).observe(args.pr,target,state));print(json.dumps(plan,indent=2,ensure_ascii=False) if args.as_json else render_text(plan));return 0
    except RuntimeError as exc:print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}",file=sys.stdout if args.as_json else sys.stderr);return ERROR_EXIT
if __name__=="__main__":raise SystemExit(main())
