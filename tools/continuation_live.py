#!/usr/bin/env python3
"""Operator CLI for the live Git-backed Continuation authority."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import continuation
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority

ERROR_EXIT=2

def flags(p):
    p.add_argument("--json",action="store_true",dest="as_json"); p.add_argument("--apply",action="store_true"); p.add_argument("--expected-plan")
def parser():
    root=argparse.ArgumentParser(prog="continuation-live",description="Live Continuation State authority")
    sub=root.add_subparsers(dest="command",required=True)
    for name in ("list","verify"): p=sub.add_parser(name); p.add_argument("--json",action="store_true",dest="as_json")
    p=sub.add_parser("show"); p.add_argument("id"); p.add_argument("--json",action="store_true",dest="as_json")
    p=sub.add_parser("create"); p.add_argument("id"); p.add_argument("--actor",required=True); p.add_argument("--remaining",action="append",required=True); p.add_argument("--next-action",required=True); p.add_argument("--branch"); p.add_argument("--pr",type=int); flags(p)
    p=sub.add_parser("advance"); p.add_argument("id"); p.add_argument("--complete",action="append",required=True); p.add_argument("--next-action"); p.add_argument("--last-good-sha"); p.add_argument("--checkpoint"); flags(p)
    p=sub.add_parser("wait"); p.add_argument("id"); p.add_argument("--blocked-by",action="append",required=True); flags(p)
    p=sub.add_parser("handoff"); p.add_argument("id"); p.add_argument("--to",required=True); p.add_argument("--next-action",required=True); flags(p)
    p=sub.add_parser("resume"); p.add_argument("id"); p.add_argument("--actor",required=True); flags(p)
    p=sub.add_parser("done"); p.add_argument("id"); flags(p)
    return root

def plan_for(authority,args):
    obs=authority.observe(); before=obs.items.get(getattr(args,"id",None))
    if args.command=="create":
        if before is not None: raise RuntimeError("CONTINUATION_ALREADY_EXISTS")
        return continuation.create(args.id,args.actor,args.remaining,args.next_action,args.branch,args.pr)
    if before is None: raise RuntimeError("CONTINUATION_FILE_MISSING")
    if args.command=="advance": return continuation.advance(before,args.complete,args.next_action,args.last_good_sha,args.checkpoint)
    if args.command=="wait": return continuation.wait(before,args.blocked_by)
    if args.command=="handoff": return continuation.handoff(before,args.to,args.next_action)
    if args.command=="resume": return continuation.resume(before,args.actor)
    if args.command=="done": return continuation.done(before)
    raise RuntimeError("CONTINUATION_COMMAND_INVALID")
def output(v,j): print(json.dumps(v,indent=2 if j else None,ensure_ascii=False))
def main(argv=None):
    args=parser().parse_args(argv); authority=GitHubContinuationAuthority()
    try:
        if args.command in {"list","verify","show"}:
            obs=authority.observe()
            if args.command=="list": payload={"schemaVersion":"ContinuationDiscovery 0.1","authorityBranch":authority.authority_branch,"authorityHead":obs.head_sha,"items":[{"id":v["id"],"actor":v["actor"],"status":v["status"],"nextAction":v["nextAction"],"stateHash":continuation.state_hash(v)} for _,v in sorted(obs.items.items())]}
            elif args.command=="verify": payload={"ok":True,"authorityBranch":authority.authority_branch,"authorityHead":obs.head_sha,"count":len(obs.items),"ids":sorted(obs.items)}
            else:
                value=obs.items.get(args.id)
                if value is None: raise RuntimeError("CONTINUATION_FILE_MISSING")
                payload={"authorityBranch":authority.authority_branch,"authorityHead":obs.head_sha,"state":value,"stateHash":continuation.state_hash(value)}
            output(payload,args.as_json); return 0
        planned=plan_for(authority,args)
        if args.apply and not args.expected_plan: raise RuntimeError("CONTINUATION_EXPECTED_PLAN_REQUIRED")
        payload=authority.apply(planned,args.expected_plan) if args.apply else {**planned,"after":planned["after"]}
        output(payload,args.as_json); return 0
    except (RuntimeError,ContinuationRemoteError) as exc:
        output({"ok":False,"error":getattr(exc,"code",str(exc)),"detail":getattr(exc,"detail","")},getattr(args,"as_json",False)); return ERROR_EXIT
if __name__=="__main__": raise SystemExit(main())
