#!/usr/bin/env python3
"""Hosted carrier for the canonical ProjectState checkpoint writer."""
from __future__ import annotations
import argparse, base64, json, subprocess, sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from tools import coordination, coordination_ownership, project_state, project_state_apply, project_state_transition, transition_protocol
from tools.agent_commands import impl as agent_impl
from tools.canonical import stable_hash
from tools.coordination_remote import ApiError, GhApiTransport, GitHubCoordinationAuthority

MARKER="MOBILIPRESENTER_PROJECT_STATE_CHECKPOINT_REQUEST_V0_1"
RESULT_MARKER="MOBILIPRESENTER_PROJECT_STATE_CHECKPOINT_RESULT_V0_1"
REQUEST_SCHEMA="HostedProjectStateCheckpointRequest 0.1"
RESULT_SCHEMA="HostedProjectStateCheckpointResult 0.1"
REPOSITORY="EAKerber/MobiliPresenter"; STATE_PATH="ops/state/project.json"
FIELDS={"schemaVersion","requestId","actor","cycleInstanceId","branch","expectedBranchHead","checkpoint","nextTransition","phase","expectedPlanHash","message","semanticAuthority","authorizesMutation"}

class Error(RuntimeError): pass

def text(v,code):
    if not isinstance(v,str) or not v.strip(): raise Error(code)
    return v.strip()

def sha(v,code,n=40):
    if not isinstance(v,str) or len(v)!=n or any(c not in "0123456789abcdef" for c in v): raise Error(code)
    return v

def validate(v):
    if not isinstance(v,dict) or set(v)!=FIELDS or v.get("schemaVersion")!=REQUEST_SCHEMA: raise Error("PROJECT_STATE_CHECKPOINT_REQUEST_INVALID")
    actor=v.get("actor")
    if not isinstance(actor,dict) or set(actor)!={"role","workerId","sessionId"}: raise Error("PROJECT_STATE_CHECKPOINT_ACTOR_INVALID")
    actor={k:text(actor.get(k),"PROJECT_STATE_CHECKPOINT_ACTOR_INVALID") for k in ("role","workerId","sessionId")}
    if actor["role"]!="manager-gitops": raise Error("PROJECT_STATE_CHECKPOINT_ROLE_FORBIDDEN")
    branch=text(v.get("branch"),"PROJECT_STATE_CHECKPOINT_BRANCH_INVALID")
    if not project_state_apply.checkpoint_branch_allowed(branch): raise Error("PROJECT_STATE_CHECKPOINT_BRANCH_FORBIDDEN")
    out={
      "schemaVersion":REQUEST_SCHEMA,"requestId":text(v.get("requestId"),"PROJECT_STATE_CHECKPOINT_REQUEST_ID_INVALID"),
      "actor":actor,"cycleInstanceId":text(v.get("cycleInstanceId"),"PROJECT_STATE_CHECKPOINT_CYCLE_INVALID"),
      "branch":branch,"expectedBranchHead":sha(v.get("expectedBranchHead"),"PROJECT_STATE_CHECKPOINT_HEAD_INVALID"),
      "checkpoint":text(v.get("checkpoint"),"PROJECT_STATE_CHECKPOINT_NAME_INVALID"),
      "nextTransition":text(v.get("nextTransition"),"PROJECT_STATE_CHECKPOINT_NEXT_INVALID"),
      "phase":None if v.get("phase") is None else text(v.get("phase"),"PROJECT_STATE_CHECKPOINT_PHASE_INVALID"),
      "expectedPlanHash":sha(v.get("expectedPlanHash"),"PROJECT_STATE_CHECKPOINT_PLAN_INVALID",64),
      "message":text(v.get("message"),"PROJECT_STATE_CHECKPOINT_MESSAGE_INVALID"),
      "semanticAuthority":False,"authorizesMutation":False}
    if v.get("semanticAuthority") is not False or v.get("authorizesMutation") is not False or out!=v: raise Error("PROJECT_STATE_CHECKPOINT_REQUEST_NOT_CANONICAL")
    return out

def request_from_event(path):
    try: event=json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc: raise Error("PROJECT_STATE_CHECKPOINT_EVENT_INVALID") from exc
    body=((event.get("comment") or {}).get("body") if isinstance(event,dict) else None)
    if not isinstance(body,str) or not body.startswith(MARKER): raise Error("PROJECT_STATE_CHECKPOINT_MARKER_INVALID")
    raw=body[len(MARKER):].strip()
    if raw.startswith("```json") and raw.endswith("```"): raw=raw[7:-3].strip()
    try: return validate(json.loads(raw))
    except json.JSONDecodeError as exc: raise Error("PROJECT_STATE_CHECKPOINT_JSON_INVALID") from exc

def run(*args):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=False)
    if p.returncode: raise Error((p.stderr or p.stdout or "COMMAND_FAILED").strip())
    return p.stdout.strip()

def ref_head(t,branch):
    try:
        r=t.request("GET",f"repos/{REPOSITORY}/git/ref/heads/{quote(branch,safe='')}")
        v=json.loads(r.body); return sha((v.get("object") or {}).get("sha"),"PROJECT_STATE_CHECKPOINT_REMOTE_REF_INVALID")
    except (ApiError,AttributeError,json.JSONDecodeError) as exc: raise Error("PROJECT_STATE_CHECKPOINT_REMOTE_REF_UNAVAILABLE") from exc

def remote_state(t,ref):
    try:
        r=t.request("GET",f"repos/{REPOSITORY}/contents/{STATE_PATH}?ref={quote(ref,safe='')}")
        p=json.loads(r.body); value=json.loads(base64.b64decode(p["content"]).decode("utf-8"))
    except Exception as exc: raise Error("PROJECT_STATE_CHECKPOINT_REMOTE_STATE_INVALID") from exc
    errors=project_state.validate_current(value)
    if errors: raise Error(f"PROJECT_STATE_CHECKPOINT_REMOTE_STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return value

def lease_proof(req,t):
    a=GitHubCoordinationAuthority(transport=t); o=a.observe()
    owner=coordination.validate_owner({"role":req["actor"]["role"],"session":req["actor"]["sessionId"],"branch":req["branch"],"pr":None})
    resource=coordination.normalize_resource(f"branch:{req['branch']}")
    try: lease=coordination_ownership.require_owned_lease(o.state,resource,owner,o.authority_now)
    except coordination.CoordinationError as exc: raise Error(f"PROJECT_STATE_CHECKPOINT_LEASE_REQUIRED:{exc.code}") from exc
    return {"resource":resource,"owner":owner,"leaseId":lease["leaseId"],"authorityHead":o.head_sha,"authorityNow":o.authority_now.isoformat().replace("+00:00","Z")}

def execute(req):
    req=validate(req); t=GhApiTransport(); git=agent_impl.observed_git()
    if git.get("branch")!=req["branch"] or git.get("head")!=req["expectedBranchHead"] or git.get("dirty") is not False: raise Error("PROJECT_STATE_CHECKPOINT_WORKTREE_MISMATCH")
    if ref_head(t,req["branch"])!=req["expectedBranchHead"]: raise Error("PROJECT_STATE_CHECKPOINT_REMOTE_HEAD_DRIFT")
    first_lease=lease_proof(req,t)
    before=project_state.load_state(); errors=project_state.validate_current(before)
    if errors: raise Error(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    plan=project_state_transition.checkpoint(before,req["checkpoint"],req["nextTransition"],req["phase"],validator=project_state.validate_current)
    transition_protocol.require_expected_plan(plan,req["expectedPlanHash"])
    local_receipt=project_state_apply.apply(plan,req["expectedPlanHash"],state_path=project_state.STATE_PATH,load_state=project_state.load_state,validator=project_state.validate_current,observe_git=agent_impl.observed_git)
    transition_protocol.validate_receipt(local_receipt,plan)
    changed=[x for x in run("git","diff","--name-only").splitlines() if x]
    if changed!=[STATE_PATH]: raise Error("PROJECT_STATE_CHECKPOINT_DELTA_INVALID")
    run("git","add","--",STATE_PATH)
    run("git","-c","user.name=github-actions[bot]","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m",req["message"])
    commit=sha(run("git","rev-parse","HEAD"),"PROJECT_STATE_CHECKPOINT_COMMIT_INVALID")
    if sha(run("git","rev-parse","HEAD^"),"PROJECT_STATE_CHECKPOINT_PARENT_INVALID")!=req["expectedBranchHead"]: raise Error("PROJECT_STATE_CHECKPOINT_PARENT_MISMATCH")
    final_lease=lease_proof(req,t)
    if final_lease["leaseId"]!=first_lease["leaseId"] or ref_head(t,req["branch"])!=req["expectedBranchHead"]: raise Error("PROJECT_STATE_CHECKPOINT_PREPUSH_DRIFT")
    run("git","push","origin",f"HEAD:refs/heads/{req['branch']}")
    if ref_head(t,req["branch"])!=commit: raise Error("PROJECT_STATE_CHECKPOINT_PUSH_READBACK_MISMATCH")
    readback=remote_state(t,commit); receipt=transition_protocol.build_receipt(plan,readback,authority_revision=commit); transition_protocol.validate_receipt(receipt,plan)
    body={"schemaVersion":RESULT_SCHEMA,"requestId":req["requestId"],"requestHash":stable_hash(req),"branch":req["branch"],"plan":plan,"leaseProof":final_lease,"localApplyReceipt":local_receipt,"commitSha":commit,"receipt":receipt,"status":"PASS","semanticAuthority":False,"authorizesMutation":False}
    return {**body,"resultHash":stable_hash(body)}

def fail(req,exc):
    body={"schemaVersion":RESULT_SCHEMA,"requestId":req.get("requestId") if isinstance(req,dict) else None,"status":"BLOCKED","blockers":[str(exc).split(":",1)[0] or exc.__class__.__name__],"detail":str(exc),"semanticAuthority":False,"authorizesMutation":False}
    return {**body,"resultHash":stable_hash(body)}

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("command",choices=("branch","execute")); p.add_argument("--event",required=True); p.add_argument("--output"); a=p.parse_args(argv); req=None
    try:
        req=request_from_event(a.event)
        if a.command=="branch": print(req["branch"]); return 0
        result=execute(req); code=0
    except Exception as exc: result=fail(req,exc); code=2
    out=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if a.output: Path(a.output).write_text(out,encoding="utf-8")
    else: print(out,end="")
    return code

if __name__=="__main__": raise SystemExit(main())
