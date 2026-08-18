#!/usr/bin/env python3
"""Deterministic operational toolbox for MobiliPresenter agents."""
from __future__ import annotations

import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from tools import project_state,publication,project_state_apply,project_state_transition
from tools import prune_plan as git_prune_plan
from tools.canonical import stable_hash
from tools.semantics.branches import parse_branch_name
from tools.semantics.observation import ObservationStatus

STATE_PATH=project_state.STATE_PATH;SCHEMA_PATH=project_state.CURRENT_SCHEMA_PATH;ERROR_EXIT=2
TOOLBOX_COMMANDS={"status","doctor","verify","checkpoint","handoff","git prune-plan"}


def run_process(args):
    proc=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=False)
    return (True,proc.stdout.strip()) if proc.returncode==0 else (False,(proc.stderr or proc.stdout).strip())
def run_git(*args):
    if shutil.which("git") is None:return False,"git executable not found"
    return run_process(["git",*args])
def run_gh_json(endpoint):
    if shutil.which("gh") is None:return False,"gh executable not found"
    ok,out=run_process(["gh","api",endpoint])
    if not ok:return False,out
    try:return True,json.loads(out)
    except json.JSONDecodeError:return False,"gh returned non-JSON output"
def ci_branch_name():
    return os.environ.get("GITHUB_HEAD_REF") or (os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE")=="branch" else None)
def observed_git():
    inside_ok,inside=run_git("rev-parse","--is-inside-work-tree")
    if not inside_ok or inside!="true":return {"available":shutil.which("git") is not None,"worktree":False}
    branch_ok,branch=run_git("branch","--show-current");head_ok,head=run_git("rev-parse","HEAD");remote_ok,remote=run_git("remote","get-url","origin");dirty_ok,porcelain=run_git("status","--porcelain")
    return {"available":True,"worktree":True,"branch":branch if branch_ok and branch else ci_branch_name(),"head":head if head_ok else None,"origin":remote if remote_ok else None,"dirty":bool(porcelain) if dirty_ok else None}
def _operations_branch(branch):
    if not isinstance(branch,str):return False
    try:identity=parse_branch_name(branch)
    except RuntimeError:return False
    if identity.get("semanticDomain")!="operations":return False
    if identity.get("grammar")=="canonical":return identity.get("declaredClass") in {"work","experiment"}
    return identity.get("grammar")=="legacy"
def git_context_check(state,observed,*,published_source_branch=None):
    if not observed.get("worktree"):return {"name":"git-context","status":"FAIL","code":"NOT_A_GIT_WORKTREE"}
    view=project_state.operational_view(state);branch=observed.get("branch");git_state=view["git"];control=git_state["controlBranch"];protected=set(git_state.get("protectedBranches") or [])
    if branch==control or (published_source_branch is not None and branch==published_source_branch):return {"name":"git-context","status":"PASS","code":None,"context":"control","branch":branch}
    if branch in protected:return {"name":"git-context","status":"PASS","code":None,"context":"protected-parallel","branch":branch}
    if _operations_branch(branch):return {"name":"git-context","status":"PASS","code":None,"context":"operations","branch":branch}
    return {"name":"git-context","status":"FAIL","code":"UNEXPECTED_BRANCH","observed":branch}
def aggregate_ci(runs):
    if not runs:return "unknown"
    meaningful=[run for run in runs if run.get("name")!="Agent Ops"]
    if not meaningful:return "unknown"
    if any(str(run.get("status","")).upper()!="COMPLETED" for run in meaningful):return "pending"
    conclusions={str(run.get("conclusion") or "").upper() for run in meaningful}
    if conclusions<={"SUCCESS","NEUTRAL","SKIPPED"}:return "green"
    if conclusions&{"FAILURE","CANCELLED","TIMED_OUT","ACTION_REQUIRED","STARTUP_FAILURE"}:return "failed"
    return "unknown"
def verification_summary(checks):
    statuses=[]
    for check in checks:
        try:statuses.append(ObservationStatus.parse(str(check.get("status") or "UNKNOWN").upper()).value)
        except RuntimeError:statuses.append(ObservationStatus.FAIL.value)
    status=ObservationStatus.FAIL.value if ObservationStatus.FAIL.value in statuses else (ObservationStatus.UNKNOWN.value if ObservationStatus.UNKNOWN.value in statuses else ObservationStatus.PASS.value)
    return {"status":status,"ok":status!=ObservationStatus.FAIL.value,"complete":status==ObservationStatus.PASS.value}
def _state_and_publication():
    state=project_state.load_state();errors=project_state.validate_current(state)
    if errors:raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    view=project_state.operational_view(state);manifest=publication.load_manifest(view["published"]["artifactManifest"]);return state,view,publication.publication_view(view,manifest)
def verify_state():
    state=project_state.load_state();checks=[];errors=project_state.validate_current(state)
    if errors:checks.extend({"name":"project-state","status":"FAIL",**error} for error in errors);view=None
    else:checks.append({"name":"project-state","status":"PASS","code":None});view=project_state.operational_view(state)
    checks.append({"name":"project-state-schema","status":"PASS" if SCHEMA_PATH.is_file() else "FAIL","code":None if SCHEMA_PATH.is_file() else "SCHEMA_FILE_MISSING"})
    publication_projection=None
    if view is None:checks.append({"name":"published-artifact-state","status":"FAIL","code":"PROJECT_STATE_INVALID"})
    else:
        try:
            manifest=publication.load_manifest(view["published"]["artifactManifest"]);publication_projection=publication.publication_view(view,manifest);checks.append({"name":"published-artifact-state","status":"PASS","code":None,"observedRelease":publication_projection["release"],"observedSourceBranch":publication_projection["sourceBranch"],"observedSourceBuildFingerprint":publication_projection["sourceBuildFingerprint"],"fingerprintKind":publication_projection["fingerprintKind"]})
        except RuntimeError as exc:checks.append({"name":"published-artifact-state","status":"FAIL","code":str(exc).split(":",1)[0]})
    for rel in ("AGENTS.md","README.md"):
        exists=(ROOT/rel).is_file();checks.append({"name":f"required:{rel}","status":"PASS" if exists else "FAIL","code":None if exists else "REQUIRED_FILE_MISSING"})
    observed=observed_git();published_source=publication_projection.get("sourceBranch") if isinstance(publication_projection,dict) else None
    if view is not None:checks.append(git_context_check(state,observed,published_source_branch=published_source))
    return {**verification_summary(checks),"checks":checks,"remote":None}
def project_summary(view):
    return {"id":view["project"]["id"],"repository":view["project"]["repository"],"controlBranch":view["git"]["controlBranch"],"initiative":view["development"]["initiative"],"phase":view["development"]["phase"],"checkpoint":view["development"]["checkpoint"],"nextTransition":view["development"]["nextTransition"]}
def command_status(as_json):
    state,view,published=_state_and_publication();payload={"project":project_summary(view),"projectStateHash":stable_hash(state),"published":published,"observedGit":observed_git(),"next":view["development"]["nextTransition"]}
    if as_json:print(json.dumps(payload,indent=2,ensure_ascii=False))
    else:print(f"PROJECT\n  id: {payload['project']['id']}\n  repository: {payload['project']['repository']}\n  phase: {payload['project']['phase']}\n  checkpoint: {payload['project']['checkpoint']}\n\nNEXT\n  {payload['next']}")
    return 0
def command_doctor(as_json):
    checks=[{"name":"python","status":"PASS" if sys.version_info>=(3,10) else "FAIL"},{"name":"git-executable","status":"PASS" if shutil.which("git") else "FAIL"},{"name":"gh-executable","status":"PASS" if shutil.which("gh") else "INFO"}]
    try:state=project_state.load_state();checks.append({"name":"project-state","status":"PASS" if not project_state.validate_current(state) else "FAIL"})
    except RuntimeError as exc:checks.append({"name":"project-state","status":"FAIL","code":str(exc).split(":",1)[0]})
    git=observed_git()
    if git.get("worktree"):checks.append({"name":"git-origin","status":"PASS" if "eakerber/mobilipresenter" in str(git.get("origin") or "").lower() else "FAIL"})
    else:checks.append({"name":"git-worktree","status":"FAIL"})
    ok=all(c["status"] in {"PASS","INFO"} for c in checks);print(json.dumps({"ok":ok,"checks":checks},indent=2,ensure_ascii=False) if as_json else "\n".join(f"{c['status']:4} {c['name']}" for c in checks));return 0 if ok else ERROR_EXIT
def command_verify(as_json):
    payload=verify_state();print(json.dumps(payload,indent=2,ensure_ascii=False) if as_json else "\n".join(f"{c['status']:7} {c['name']}" for c in payload["checks"]));return 0 if payload["status"]=="PASS" else ERROR_EXIT
def command_checkpoint(as_json,args):
    state=project_state.load_state();plan=project_state_transition.checkpoint(state,args.checkpoint,args.next_transition,args.phase,validator=project_state.validate_current);payload=project_state_apply.apply(plan,args.expected_plan,state_path=STATE_PATH,load_state=project_state.load_state,validator=project_state.validate_current,observe_git=observed_git) if args.apply else plan;print(json.dumps(payload,indent=2,ensure_ascii=False) if as_json else ("APPLIED" if args.apply else "PLAN"));return 0
def recent_commits(control_branch):
    ok,out=run_git("log","--oneline","--decorate=no",f"{control_branch}..HEAD","-n","20");return {"available":True,"entries":out.splitlines()} if ok else {"available":False,"reason":out}
def command_handoff(as_json):
    state,view,published=_state_and_publication();observed=observed_git();verify=verify_state();project=project_summary(view);payload={"schemaVersion":"AgentHandoff 2.1","projectStateHash":stable_hash(state),"project":project,"publication":published,"observedGit":observed,"verification":verify,"recentCommits":recent_commits(project["controlBranch"]) if observed.get("worktree") else {"available":False},"nextTransition":project["nextTransition"],"note":"Derived snapshot; not a new source of truth."};print(json.dumps(payload,indent=2,ensure_ascii=False) if as_json else f"HANDOFF\n  verify: {verify['status']}\n  next: {payload['nextTransition']}");return 0 if verify["status"]=="PASS" else ERROR_EXIT
def command_git_prune_plan(as_json):return git_prune_plan.command_generate(as_json)
def main():
    parser=argparse.ArgumentParser(prog="agent",description="MobiliPresenter deterministic operational toolbox");parser.add_argument("command",choices=("status","doctor","verify","checkpoint","handoff","git"));parser.add_argument("subcommand",nargs="?");parser.add_argument("--json",action="store_true",dest="as_json");parser.add_argument("--to",dest="checkpoint");parser.add_argument("--next",dest="next_transition");parser.add_argument("--phase");parser.add_argument("--apply",action="store_true");parser.add_argument("--expected-plan");args=parser.parse_args()
    try:
        if args.command=="status":return command_status(args.as_json)
        if args.command=="doctor":return command_doctor(args.as_json)
        if args.command=="verify":return command_verify(args.as_json)
        if args.command=="checkpoint":
            if not args.checkpoint or not args.next_transition:raise RuntimeError("CHECKPOINT_ARGS_REQUIRED: --to and --next")
            return command_checkpoint(args.as_json,args)
        if args.command=="git":
            if args.subcommand!="prune-plan":raise RuntimeError("GIT_SUBCOMMAND_REQUIRED: prune-plan")
            if args.apply:raise RuntimeError("UNSUPPORTED_TRANSITION: prune planning is read-only; destructive apply is a separately guarded operation")
            return command_git_prune_plan(args.as_json)
        if args.subcommand is not None:raise RuntimeError(f"UNEXPECTED_SUBCOMMAND:{args.subcommand}")
        return command_handoff(args.as_json)
    except RuntimeError as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}",file=sys.stdout if args.as_json else sys.stderr);return ERROR_EXIT
if __name__=="__main__":raise SystemExit(main())
