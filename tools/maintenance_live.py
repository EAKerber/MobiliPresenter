#!/usr/bin/env python3
"""Maintenance Inspect using the live Continuation Git authority."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import agent, continuation, maintenance_inspect
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority

ERROR_EXIT=2

def snapshot(authority):
    observed=authority.observe()
    items=[]
    for cid,value in sorted(observed.items.items()):
        items.append({"id":value["id"],"actor":value["actor"],"status":value["status"],"branch":value["branch"],"prNumber":value["prNumber"],"completed":value["completed"],"remaining":value["remaining"],"nextAction":value["nextAction"],"lastKnownGood":value["lastKnownGood"],"blockedBy":value["blockedBy"],"handoffTo":value["handoffTo"],"stateHash":continuation.state_hash(value)})
    return observed,items

def inspect():
    state=agent.load_json(agent.STATE_PATH); errors=agent.validate_state_shape(state)
    if errors: raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    authority=GitHubContinuationAuthority(); cont_obs,items=snapshot(authority)
    payload=maintenance_inspect.build_inspection(state,agent.verify_state(include_remote=True),agent.observed_git(),maintenance_inspect.capability_snapshot(),remote_requested=True,pull_requests=maintenance_inspect.observe_open_prs(state),coordination_state=maintenance_inspect.observe_coordination(),continuations=items)
    payload["continuationAuthority"]={"available":True,"authorityBranch":authority.authority_branch,"authorityHead":cont_obs.head_sha,"count":len(items)}
    body={k:v for k,v in payload.items() if k!="inspectionHash"}; payload["inspectionHash"]=maintenance_inspect.capability_gates.stable_hash(body)
    return payload

def main(argv=None):
    p=argparse.ArgumentParser(prog="maintenance-live"); p.add_argument("--json",action="store_true",dest="as_json"); args=p.parse_args(argv)
    try:
        payload=inspect(); print(json.dumps(payload,indent=2 if args.as_json else None,ensure_ascii=False)); return 0
    except (RuntimeError,ContinuationRemoteError) as exc:
        print(json.dumps({"ok":False,"error":getattr(exc,"code",str(exc)),"detail":getattr(exc,"detail","")},ensure_ascii=False)); return ERROR_EXIT
if __name__=="__main__": raise SystemExit(main())
