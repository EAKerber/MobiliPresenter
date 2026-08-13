#!/usr/bin/env python3
"""CLI for deterministic capability Gate transitions."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import capability_gates as gates
from tools import capability_transition as tx
from tools.capability_apply import apply
ERROR_EXIT=2


def gate_spec(raw):
    if "=" not in raw: raise RuntimeError("CAPABILITY_GATE_SPEC_INVALID")
    gid,test=raw.split("=",1); return {"id":tx.ident(gid.strip(),"CAPABILITY_GATE_ID_INVALID"),"test":tx.text(test,"CAPABILITY_GATE_TEST_INVALID")}


def flags(p,evidence=False):
    p.add_argument("--json",action="store_true",dest="as_json"); p.add_argument("--apply",action="store_true"); p.add_argument("--expected-plan")
    if evidence: p.add_argument("--evidence",action="append",default=[])


def parser():
    root=argparse.ArgumentParser(prog="capability-lifecycle",description="Plan/apply capability Gate lifecycle transitions")
    sub=root.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init"); p.add_argument("capability_id"); p.add_argument("--gate",action="append",default=[]); p.add_argument("--max-empty-rounds",type=int,default=3); p.add_argument("--defer-reason"); flags(p)
    p=sub.add_parser("gate-add"); p.add_argument("capability_id"); p.add_argument("gate_id"); p.add_argument("--test",required=True); flags(p)
    p=sub.add_parser("next"); p.add_argument("capability_id"); p.add_argument("gate_ids",nargs="+"); flags(p)
    for name in ("pass","fail"):
        p=sub.add_parser(name); p.add_argument("capability_id"); p.add_argument("gate_id"); flags(p,True)
    p=sub.add_parser("defer"); p.add_argument("capability_id"); p.add_argument("--reason",required=True); flags(p)
    p=sub.add_parser("review-limit"); p.add_argument("capability_id"); p.add_argument("--max",type=int,required=True,dest="new_max"); p.add_argument("--reason",required=True); flags(p)
    p=sub.add_parser("promote"); p.add_argument("capability_id"); flags(p,True)
    p=sub.add_parser("disable"); p.add_argument("capability_id"); p.add_argument("--reason",required=True); flags(p)
    return root


def make_plan(args):
    if args.command=="init": return tx.init(args.capability_id,[gate_spec(x) for x in args.gate],max_empty_rounds=args.max_empty_rounds,defer_reason=args.defer_reason)
    before=gates.load_capability(args.capability_id)
    if args.command=="gate-add": return tx.gate_add(before,args.gate_id,args.test)
    if args.command=="next": return tx.select_next(before,args.gate_ids)
    if args.command=="pass": return tx.passed(before,args.gate_id,args.evidence)
    if args.command=="fail": return tx.failed(before,args.gate_id,args.evidence)
    if args.command=="defer": return tx.defer(before,args.reason)
    if args.command=="review-limit": return tx.review_limit(before,args.new_max,args.reason)
    if args.command=="promote": return tx.promote(before,args.evidence)
    if args.command=="disable": return tx.disable(before,args.reason)
    raise RuntimeError("CAPABILITY_COMMAND_INVALID")


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        plan=make_plan(args)
        if args.apply and not args.expected_plan: raise RuntimeError("CAPABILITY_EXPECTED_PLAN_REQUIRED")
        payload=apply(plan,args.expected_plan) if args.apply else {k:v for k,v in plan.items() if k!="after"}
        print(json.dumps(payload,indent=2 if args.as_json else None,ensure_ascii=False)); return 0
    except RuntimeError as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False)); return ERROR_EXIT


if __name__=="__main__": raise SystemExit(main())
