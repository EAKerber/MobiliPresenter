#!/usr/bin/env python3
"""Evidence-based branch sanitation planner for MobiliPresenter.

GitPrunePlan 0.3 is read-only. It classifies branch refs from explicit
protection and objective Git/PR evidence. Branch names are descriptive only:
they never grant retention, protection, lifecycle state, or delete eligibility.
"""
from __future__ import annotations
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import project_state,publication
from tools.canonical import stable_hash
from tools.semantics.branches import parse_branch_name
STATE_PATH=project_state.STATE_PATH;ERROR_EXIT=2;SCHEMA_VERSION="GitPrunePlan 0.3"

def run_process(args):
    proc=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=False)
    if proc.returncode!=0:return False,(proc.stderr or proc.stdout).strip()
    return True,proc.stdout.strip()
def run_git(*args):
    if shutil.which("git") is None:return False,"git executable not found"
    return run_process(["git",*args])
def run_gh_json(endpoint):
    if shutil.which("gh") is None:return False,"gh executable not found"
    ok,output=run_process(["gh","api",endpoint])
    if not ok:return False,output
    try:return True,json.loads(output)
    except json.JSONDecodeError:return False,"gh returned non-JSON output"
def load_state():
    state=project_state.load_state();errors=project_state.validate_current(state)
    if errors:raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return state
def branch_refs_with_source():
    ok,output=run_git("for-each-ref","--format=%(refname:short)\t%(objectname)","refs/remotes/origin");refs={}
    if ok:
        for line in output.splitlines():
            if not line.strip():continue
            name,sha=line.split("\t",1)
            if name in {"origin","origin/HEAD"} or not name.startswith("origin/"):continue
            refs[name.removeprefix("origin/")]=sha
    if refs:return refs,"remote-git-refs"
    ok,output=run_git("for-each-ref","--format=%(refname:short)\t%(objectname)","refs/heads")
    if not ok:raise RuntimeError(f"BRANCH_INVENTORY_FAILED:{output}")
    for line in output.splitlines():
        if line.strip():name,sha=line.split("\t",1);refs[name]=sha
    return refs,"local-heads"
def _normalize_pr(item,repository):
    head=item.get("head")
    if not isinstance(head,dict):return None
    ref=head.get("ref");sha=head.get("sha")
    if not isinstance(ref,str) or not isinstance(sha,str):return None
    head_repo=head.get("repo")
    if isinstance(head_repo,dict):
        full_name=head_repo.get("full_name")
        if isinstance(full_name,str) and full_name.casefold()!=repository.casefold():return None
    return {"number":item.get("number"),"state":item.get("state"),"draft":bool(item.get("draft")),"merged":bool(item.get("merged_at")),"mergedAt":item.get("merged_at"),"headRef":ref,"headSha":sha,"baseRef":item.get("base",{}).get("ref") if isinstance(item.get("base"),dict) else None}
def observe_pull_requests(state):
    repository=project_state.operational_view(state)["project"]["repository"];normalized=[]
    for page in range(1,21):
        ok,payload=run_gh_json(f"repos/{repository}/pulls?state=all&per_page=100&page={page}")
        if not ok or not isinstance(payload,list):return False,[],"PR_HISTORY_READ_FAILED"
        for item in payload:
            if isinstance(item,dict):
                pr=_normalize_pr(item,repository)
                if pr is not None:normalized.append(pr)
        if len(payload)<100:return True,normalized,None
    return False,[],"PR_HISTORY_PAGINATION_LIMIT"
def ancestry_for_ref(sha,control_sha):
    if sha==control_sha:return "identical-to-control"
    ancestor,_=run_git("merge-base","--is-ancestor",sha,control_sha)
    if ancestor:return "ancestor-of-control"
    reverse,_=run_git("merge-base","--is-ancestor",control_sha,sha)
    if reverse:return "control-ancestor-of-branch"
    base_ok,base=run_git("merge-base",sha,control_sha)
    if base_ok and base:return "diverged"
    return "unknown"
def observe_ancestry(refs,control_branch):
    control_sha=refs.get(control_branch)
    if not control_sha:return {branch:"unknown" for branch in refs},False
    result={branch:ancestry_for_ref(sha,control_sha) for branch,sha in refs.items()};return result,all(value!="unknown" for value in result.values())
def _pr_index(pull_requests):
    by_branch={}
    for pr in pull_requests:
        ref=pr.get("headRef")
        if isinstance(ref,str):by_branch.setdefault(ref,[]).append(pr)
    for prs in by_branch.values():prs.sort(key=lambda pr:int(pr.get("number") or 0))
    return by_branch
def _protection_reasons(view,branch,open_pr_heads,*,published_source_branch=None):
    git_state=view["git"];reasons=[]
    if branch==git_state.get("controlBranch"):reasons.append("control-branch")
    if isinstance(published_source_branch,str) and branch==published_source_branch:reasons.append("published-branch")
    if branch==git_state.get("activeDevelopmentBranch"):reasons.append("active-development")
    if branch in set(git_state.get("protectedBranches") or []):reasons.append("project-state-protected")
    if branch in open_pr_heads:reasons.append("open-pr-head")
    return reasons
def build_prune_plan(state,refs,pull_requests,ancestry,*,branch_inventory_complete=True,ancestry_complete=True,branch_inventory_source="fixture",remote_observation_error=None,published_source_branch=None):
    view=project_state.operational_view(state);git_state=view["git"];control_branch=git_state["controlBranch"];control_sha=refs.get(control_branch);pr_history_complete=pull_requests is not None;pr_index=_pr_index(pull_requests or []);open_pr_heads={str(pr["headRef"]) for pr in (pull_requests or []) if pr.get("state")=="open" and isinstance(pr.get("headRef"),str)};entries=[]
    for branch,sha in sorted(refs.items()):
        protections=_protection_reasons(view,branch,open_pr_heads,published_source_branch=published_source_branch);branch_prs=pr_index.get(branch,[]);ancestry_status=ancestry.get(branch,"unknown") if ancestry is not None else "unknown";provenance=[];strong=[]
        for pr in branch_prs:
            head_matches=pr.get("headSha")==sha;provenance.append({"number":pr.get("number"),"state":pr.get("state"),"merged":bool(pr.get("merged")),"headSha":pr.get("headSha"),"headMatchesCurrent":head_matches})
            if head_matches and pr.get("merged"):strong.append(f"merged-pr:{pr.get('number')}")
        if ancestry_status in {"ancestor-of-control","identical-to-control"}:strong.append(ancestry_status)
        if protections:action,reason,auto="keep","protected",False
        elif strong:action,reason,auto="delete-candidate","strong-observed-evidence",True
        else:action,reason,auto="review","insufficient-delete-evidence",False
        try:identity=parse_branch_name(branch)
        except RuntimeError:identity={"name":branch,"grammar":"invalid","namespace":None,"declaredClass":None,"domain":None,"semanticDomain":None,"legacyAlias":False,"slug":None}
        entries.append({"branch":branch,"sha":sha,"branchIdentity":identity,"action":action,"reason":reason,"autoDeleteEligible":auto,"protections":protections,"ancestryToControl":ancestry_status,"prProvenance":provenance,"evidence":sorted(set(strong)),"duplicateOf":[]})
    by_sha={}
    for entry in entries:by_sha.setdefault(entry["sha"],[]).append(entry)
    for same_sha_entries in by_sha.values():
        integrated=[entry for entry in same_sha_entries if entry["action"]=="delete-candidate"]
        if not integrated:continue
        integrated_names=sorted(entry["branch"] for entry in integrated)
        for entry in same_sha_entries:
            if entry["action"]!="review":continue
            duplicates=[name for name in integrated_names if name!=entry["branch"]]
            if duplicates:entry["duplicateOf"]=duplicates;entry["evidence"].append(f"duplicate-of-integrated-head:{duplicates[0]}");entry["action"]="delete-candidate";entry["reason"]="exact-duplicate-of-integrated-head";entry["autoDeleteEligible"]=True
    observations_complete=bool(branch_inventory_complete and pr_history_complete and ancestry_complete and control_sha is not None)
    body={"schemaVersion":SCHEMA_VERSION,"repository":view["project"]["repository"],"controlBranch":control_branch,"controlSha":control_sha,"branchCount":len(refs),"observations":{"complete":observations_complete,"branchInventoryComplete":bool(branch_inventory_complete),"branchInventorySource":branch_inventory_source,"prHistoryComplete":pr_history_complete,"prHistoryError":remote_observation_error,"ancestryComplete":bool(ancestry_complete)},"execution":{"executorAvailable":True,"requiresPlanFile":True,"requiresExpectedPlan":True,"requiresExplicitAuthorization":True},"openPrHeads":sorted(open_pr_heads),"entries":entries,"note":"Evidence-only sanitation plan. Names never authorize retention or deletion; execution requires this exact materialized plan, explicit plan identity, authorization, drift checks, and readback."}
    return {**body,"planHash":stable_hash(body)}
def build_live_plan():
    state=load_state();view=project_state.operational_view(state);manifest=publication.load_manifest(view["published"]["artifactManifest"]);published=publication.publication_view(view,manifest);refs,source=branch_refs_with_source();prs_ok,prs,prs_error=observe_pull_requests(state);ancestry,ancestry_complete=observe_ancestry(refs,view["git"]["controlBranch"])
    return build_prune_plan(state,refs,prs if prs_ok else None,ancestry,branch_inventory_complete=source=="remote-git-refs",ancestry_complete=ancestry_complete,branch_inventory_source=source,remote_observation_error=None if prs_ok else prs_error,published_source_branch=published["sourceBranch"])
def command(as_json):
    try:plan=build_live_plan()
    except RuntimeError as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if as_json else f"BLOCKED\n{exc}");return ERROR_EXIT
    if as_json:print(json.dumps(plan,indent=2,ensure_ascii=False))
    else:
        counts={}
        for entry in plan["entries"]:counts[entry["action"]]=counts.get(entry["action"],0)+1
        print("GIT PRUNE PLAN 0.3");print(f"  branches: {plan['branchCount']}");print(f"  keep: {counts.get('keep',0)}");print(f"  delete-candidate: {counts.get('delete-candidate',0)}");print(f"  review: {counts.get('review',0)}");print(f"  observations complete: {plan['observations']['complete']}");print(f"  planHash: {plan['planHash']}")
    return 0
def main():
    parser=argparse.ArgumentParser(description="Read-only evidence-based Git branch sanitation planner");parser.add_argument("--json",action="store_true",dest="as_json");args=parser.parse_args();return command(args.as_json)
if __name__=="__main__":raise SystemExit(main())
