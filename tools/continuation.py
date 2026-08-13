#!/usr/bin/env python3
"""Persistent deterministic continuation state for work that must survive chat loss."""
from __future__ import annotations
import argparse, copy, json, os, re, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.capability_gates import stable_hash
DIR=ROOT/"ops/continuations"; SCHEMA="ContinuationState 0.1"; PLAN_SCHEMA="ContinuationTransitionPlan 0.1"; ERROR_EXIT=2
STATUSES={"READY","IN_PROGRESS","WAITING","HANDOFF","DONE"}; ID_RE=re.compile(r"^[a-z0-9][a-z0-9-]*$")

def text(v,code):
    if not isinstance(v,str) or not v.strip(): raise RuntimeError(code)
    return v.strip()
def strings(v,code):
    if not isinstance(v,list): raise RuntimeError(code)
    out=[]
    for x in v:
        x=text(x,code)
        if x in out: raise RuntimeError(code)
        out.append(x)
    return out
def state_hash(v): return None if v is None else stable_hash(v)
def load_json(path):
    try: v=json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc: raise RuntimeError("CONTINUATION_FILE_MISSING") from exc
    except json.JSONDecodeError as exc: raise RuntimeError("CONTINUATION_JSON_INVALID") from exc
    if not isinstance(v,dict): raise RuntimeError("CONTINUATION_ROOT_INVALID")
    return v

def validate(v,expected_id=None):
    errors=[]; fields={"schemaVersion","id","actor","status","branch","prNumber","completed","remaining","nextAction","lastKnownGood","blockedBy","handoffTo"}
    if set(v)!=fields: errors.append("CONTINUATION_FIELDS_INVALID")
    if v.get("schemaVersion")!=SCHEMA: errors.append("CONTINUATION_SCHEMA_UNSUPPORTED")
    cid=v.get("id")
    if not isinstance(cid,str) or not ID_RE.fullmatch(cid): errors.append("CONTINUATION_ID_INVALID")
    elif expected_id and cid!=expected_id: errors.append("CONTINUATION_ID_PATH_MISMATCH")
    if not isinstance(v.get("actor"),str) or not v["actor"].strip(): errors.append("CONTINUATION_ACTOR_INVALID")
    status=v.get("status")
    if status not in STATUSES: errors.append("CONTINUATION_STATUS_INVALID")
    branch=v.get("branch"); pr=v.get("prNumber")
    if branch is not None and (not isinstance(branch,str) or not branch.strip()): errors.append("CONTINUATION_BRANCH_INVALID")
    if pr is not None and (type(pr) is not int or pr<=0): errors.append("CONTINUATION_PR_INVALID")
    if pr is not None and branch is None: errors.append("CONTINUATION_PR_REQUIRES_BRANCH")
    try: completed=strings(v.get("completed"),"CONTINUATION_COMPLETED_INVALID")
    except RuntimeError as exc: errors.append(str(exc)); completed=[]
    try: remaining=strings(v.get("remaining"),"CONTINUATION_REMAINING_INVALID")
    except RuntimeError as exc: errors.append(str(exc)); remaining=[]
    if set(completed)&set(remaining): errors.append("CONTINUATION_WORK_OVERLAP")
    next_action=v.get("nextAction")
    if next_action is not None and (not isinstance(next_action,str) or not next_action.strip()): errors.append("CONTINUATION_NEXT_ACTION_INVALID")
    last=v.get("lastKnownGood")
    if not isinstance(last,dict) or set(last)!={"sha","checkpoint"}: errors.append("CONTINUATION_LAST_GOOD_INVALID")
    else:
        sha=last.get("sha"); cp=last.get("checkpoint")
        if sha is not None and (not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha)): errors.append("CONTINUATION_LAST_GOOD_SHA_INVALID")
        if cp is not None and (not isinstance(cp,str) or not cp.strip()): errors.append("CONTINUATION_LAST_GOOD_CHECKPOINT_INVALID")
    try: blocked=strings(v.get("blockedBy"),"CONTINUATION_BLOCKERS_INVALID")
    except RuntimeError as exc: errors.append(str(exc)); blocked=[]
    target=v.get("handoffTo")
    if target is not None and (not isinstance(target,str) or not target.strip()): errors.append("CONTINUATION_HANDOFF_TO_INVALID")
    if status=="DONE" and (remaining or next_action is not None or blocked or target is not None): errors.append("CONTINUATION_DONE_STATE_INVALID")
    if status=="WAITING" and (not blocked or next_action is None or target is not None): errors.append("CONTINUATION_WAITING_STATE_INVALID")
    if status=="HANDOFF" and (target is None or next_action is None or blocked): errors.append("CONTINUATION_HANDOFF_STATE_INVALID")
    if status in {"READY","IN_PROGRESS"} and (blocked or target is not None or (remaining and next_action is None)): errors.append("CONTINUATION_ACTIVE_STATE_INVALID")
    return errors
def valid(v,expected_id=None):
    e=validate(v,expected_id)
    if e: raise RuntimeError(e[0])
    return v
def load(cid):
    if not ID_RE.fullmatch(cid): raise RuntimeError("CONTINUATION_ID_INVALID")
    return valid(load_json(DIR/f"{cid}.json"),cid)
def discover():
    if not DIR.is_dir(): return []
    return [valid(load_json(p),p.stem) for p in sorted(DIR.glob("*.json"))]
def plan(action,before,after,details=None):
    if before is not None: valid(before,after["id"])
    valid(after,after["id"])
    core={"schemaVersion":PLAN_SCHEMA,"id":after["id"],"action":action,"beforeStateHash":state_hash(before),"afterStateHash":state_hash(after),"details":details or {}}
    return {**core,"planHash":stable_hash(core),"after":after}
def create(cid,actor,remaining,next_action,branch=None,pr=None):
    if not ID_RE.fullmatch(cid): raise RuntimeError("CONTINUATION_ID_INVALID")
    actor=text(actor,"CONTINUATION_ACTOR_INVALID"); remaining=strings(remaining,"CONTINUATION_REMAINING_INVALID")
    if not remaining: raise RuntimeError("CONTINUATION_CREATE_REQUIRES_WORK")
    if pr is not None and (type(pr) is not int or pr<=0): raise RuntimeError("CONTINUATION_PR_INVALID")
    if branch is not None: branch=text(branch,"CONTINUATION_BRANCH_INVALID")
    after={"schemaVersion":SCHEMA,"id":cid,"actor":actor,"status":"READY","branch":branch,"prNumber":pr,"completed":[],"remaining":remaining,"nextAction":text(next_action,"CONTINUATION_NEXT_ACTION_INVALID"),"lastKnownGood":{"sha":None,"checkpoint":None},"blockedBy":[],"handoffTo":None}
    return plan("create",None,after)
def advance(before,done,next_action=None,sha=None,checkpoint=None):
    after=copy.deepcopy(valid(before))
    if after["status"] not in {"READY","IN_PROGRESS"}: raise RuntimeError("CONTINUATION_ADVANCE_STATUS_INVALID")
    done=strings(done,"CONTINUATION_COMPLETE_INVALID")
    if not done: raise RuntimeError("CONTINUATION_ADVANCE_REQUIRES_COMPLETION")
    if any(x not in after["remaining"] for x in done): raise RuntimeError("CONTINUATION_COMPLETE_NOT_REMAINING")
    after["completed"].extend(done); after["remaining"]=[x for x in after["remaining"] if x not in set(done)]; after["status"]="IN_PROGRESS"
    after["nextAction"]=text(next_action,"CONTINUATION_NEXT_ACTION_REQUIRED") if after["remaining"] else None
    if sha is not None:
        if not re.fullmatch(r"[0-9a-f]{40}",sha): raise RuntimeError("CONTINUATION_LAST_GOOD_SHA_INVALID")
        after["lastKnownGood"]["sha"]=sha
    if checkpoint is not None: after["lastKnownGood"]["checkpoint"]=text(checkpoint,"CONTINUATION_LAST_GOOD_CHECKPOINT_INVALID")
    return plan("advance",before,after,{"completed":done})
def wait(before,blocked):
    after=copy.deepcopy(valid(before))
    if after["status"] not in {"READY","IN_PROGRESS"}: raise RuntimeError("CONTINUATION_WAIT_STATUS_INVALID")
    blocked=strings(blocked,"CONTINUATION_BLOCKERS_INVALID")
    if not blocked: raise RuntimeError("CONTINUATION_WAIT_REQUIRES_BLOCKER")
    if after["nextAction"] is None: raise RuntimeError("CONTINUATION_WAIT_REQUIRES_NEXT_ACTION")
    after["status"]="WAITING"; after["blockedBy"]=blocked; return plan("wait",before,after)
def handoff(before,target,next_action):
    after=copy.deepcopy(valid(before))
    if after["status"] not in {"READY","IN_PROGRESS"}: raise RuntimeError("CONTINUATION_HANDOFF_STATUS_INVALID")
    after["status"]="HANDOFF"; after["handoffTo"]=text(target,"CONTINUATION_HANDOFF_TO_INVALID"); after["nextAction"]=text(next_action,"CONTINUATION_NEXT_ACTION_INVALID"); after["blockedBy"]=[]
    return plan("handoff",before,after)
def resume(before,actor):
    after=copy.deepcopy(valid(before)); actor=text(actor,"CONTINUATION_ACTOR_INVALID")
    if after["status"] not in {"WAITING","HANDOFF"}: raise RuntimeError("CONTINUATION_RESUME_STATUS_INVALID")
    if after["status"]=="HANDOFF" and after["handoffTo"]!=actor: raise RuntimeError("CONTINUATION_HANDOFF_ACTOR_MISMATCH")
    after["actor"]=actor; after["status"]="IN_PROGRESS"; after["blockedBy"]=[]; after["handoffTo"]=None; return plan("resume",before,after)
def done(before):
    after=copy.deepcopy(valid(before))
    if after["status"] not in {"READY","IN_PROGRESS"}: raise RuntimeError("CONTINUATION_DONE_STATUS_INVALID")
    if after["remaining"]: raise RuntimeError("CONTINUATION_DONE_REMAINING_WORK")
    after["status"]="DONE"; after["nextAction"]=None; return plan("done",before,after)
def apply(p,expected):
    if expected!=p["planHash"]: raise RuntimeError("CONTINUATION_PLAN_HASH_MISMATCH")
    path=DIR/f"{p['id']}.json"
    if p["beforeStateHash"] is None:
        if path.exists(): raise RuntimeError("CONTINUATION_ALREADY_EXISTS")
    elif state_hash(load(p["id"]))!=p["beforeStateHash"]: raise RuntimeError("CONTINUATION_PLAN_STALE")
    DIR.mkdir(parents=True,exist_ok=True); encoded=json.dumps(p["after"],indent=2,ensure_ascii=False)+"\n"
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=DIR,delete=False) as h: h.write(encoded); tmp=h.name
    os.replace(tmp,path); rb=load(p["id"])
    if state_hash(rb)!=p["afterStateHash"]: raise RuntimeError("CONTINUATION_READBACK_MISMATCH")
    return {"ok":True,"applied":True,"id":p["id"],"action":p["action"],"planHash":p["planHash"],"stateHash":p["afterStateHash"]}
def flags(p): p.add_argument("--json",action="store_true",dest="as_json"); p.add_argument("--apply",action="store_true"); p.add_argument("--expected-plan")
def parser():
    root=argparse.ArgumentParser(prog="continuation"); sub=root.add_subparsers(dest="command",required=True)
    for name in ("list","verify"): p=sub.add_parser(name); p.add_argument("--json",action="store_true",dest="as_json")
    p=sub.add_parser("show"); p.add_argument("id"); p.add_argument("--json",action="store_true",dest="as_json")
    p=sub.add_parser("create"); p.add_argument("id"); p.add_argument("--actor",required=True); p.add_argument("--remaining",action="append",required=True); p.add_argument("--next-action",required=True); p.add_argument("--branch"); p.add_argument("--pr",type=int); flags(p)
    p=sub.add_parser("advance"); p.add_argument("id"); p.add_argument("--complete",action="append",required=True); p.add_argument("--next-action"); p.add_argument("--last-good-sha"); p.add_argument("--checkpoint"); flags(p)
    p=sub.add_parser("wait"); p.add_argument("id"); p.add_argument("--blocked-by",action="append",required=True); flags(p)
    p=sub.add_parser("handoff"); p.add_argument("id"); p.add_argument("--to",required=True); p.add_argument("--next-action",required=True); flags(p)
    p=sub.add_parser("resume"); p.add_argument("id"); p.add_argument("--actor",required=True); flags(p)
    p=sub.add_parser("done"); p.add_argument("id"); flags(p)
    return root
def output(v,j): print(json.dumps(v,indent=2 if j else None,ensure_ascii=False))
def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="list":
            vals=discover(); output({"schemaVersion":"ContinuationDiscovery 0.1","items":[{"id":v["id"],"actor":v["actor"],"status":v["status"],"nextAction":v["nextAction"],"stateHash":state_hash(v)} for v in vals]},args.as_json); return 0
        if args.command=="show": v=load(args.id); output({"state":v,"stateHash":state_hash(v)},args.as_json); return 0
        if args.command=="verify": vals=discover(); output({"ok":True,"count":len(vals),"ids":[v["id"] for v in vals]},args.as_json); return 0
        if args.command=="create": p=create(args.id,args.actor,args.remaining,args.next_action,args.branch,args.pr)
        else:
            before=load(args.id)
            if args.command=="advance": p=advance(before,args.complete,args.next_action,args.last_good_sha,args.checkpoint)
            elif args.command=="wait": p=wait(before,args.blocked_by)
            elif args.command=="handoff": p=handoff(before,args.to,args.next_action)
            elif args.command=="resume": p=resume(before,args.actor)
            elif args.command=="done": p=done(before)
            else: raise RuntimeError("CONTINUATION_COMMAND_INVALID")
        if args.apply and not args.expected_plan: raise RuntimeError("CONTINUATION_EXPECTED_PLAN_REQUIRED")
        output(apply(p,args.expected_plan) if args.apply else p,args.as_json); return 0
    except RuntimeError as exc: output({"ok":False,"error":str(exc)},getattr(args,"as_json",False)); return ERROR_EXIT
if __name__=="__main__": raise SystemExit(main())
