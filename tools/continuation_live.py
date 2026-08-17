#!/usr/bin/env python3
"""Operator CLI for the canonical live WorkItem authority."""
from __future__ import annotations

import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import continuation,continuation_transition as transition,work_graph
from tools.continuation_remote import ContinuationRemoteError,GitHubContinuationAuthority
ERROR_EXIT=2

def flags(p):p.add_argument('--json',action='store_true',dest='as_json');p.add_argument('--apply',action='store_true');p.add_argument('--expected-plan')
def parser():
    root=argparse.ArgumentParser(prog='continuation-live',description='Live WorkItem authority');sub=root.add_subparsers(dest='command',required=True)
    for n in ('list','verify'):c=sub.add_parser(n);c.add_argument('--json',action='store_true',dest='as_json')
    c=sub.add_parser('show');c.add_argument('id');c.add_argument('--json',action='store_true',dest='as_json')
    c=sub.add_parser('create');c.add_argument('id');c.add_argument('--worker-id',required=True);c.add_argument('--remaining',action='append',required=True);c.add_argument('--next-action',required=True);c.add_argument('--branch');c.add_argument('--pr',type=int);c.add_argument('--depends-on',action='append');flags(c)
    c=sub.add_parser('advance');c.add_argument('id');c.add_argument('--complete',action='append',required=True);c.add_argument('--next-action');c.add_argument('--last-good-sha');c.add_argument('--checkpoint');flags(c)
    c=sub.add_parser('wait');c.add_argument('id');c.add_argument('--blocker',action='append',required=True);flags(c)
    c=sub.add_parser('handoff');c.add_argument('id');c.add_argument('--to-worker',required=True);c.add_argument('--next-action',required=True);flags(c)
    c=sub.add_parser('resume');c.add_argument('id');c.add_argument('--worker-id',required=True);flags(c)
    c=sub.add_parser('done');c.add_argument('id');flags(c)
    c=sub.add_parser('bind-execution');c.add_argument('id');c.add_argument('--branch');c.add_argument('--pr',type=int);flags(c)
    c=sub.add_parser('restart');c.add_argument('id');c.add_argument('--remaining',action='append',required=True);c.add_argument('--next-action',required=True);flags(c)
    return root

def plan_for(a,args):
    o=a.observe();before=o.items.get(getattr(args,'id',None));inventory=[v for _,v in sorted(o.items.items())]
    if args.command=='create':
        if before is not None:raise RuntimeError('CONTINUATION_ALREADY_EXISTS')
        return transition.create(args.id,args.worker_id,args.remaining,args.next_action,args.branch,args.pr,depends_on=args.depends_on)
    if before is None:raise RuntimeError('CONTINUATION_FILE_MISSING')
    if args.command=='advance':return transition.advance(before,args.complete,args.next_action,args.last_good_sha,args.checkpoint,inventory=inventory)
    if args.command=='wait':return transition.wait(before,args.blocker)
    if args.command=='handoff':return transition.handoff(before,args.to_worker,args.next_action)
    if args.command=='resume':return transition.resume(before,args.worker_id)
    if args.command=='done':return transition.done(before,inventory=inventory)
    if args.command=='bind-execution':return transition.bind_execution(before,args.branch,args.pr)
    if args.command=='restart':return transition.restart(before,args.remaining,args.next_action)
    raise RuntimeError('CONTINUATION_COMMAND_INVALID')

def summary(v):
    x=continuation.operational_view(v);return {'id':x['id'],'workerId':x['workerId'],'status':x['status'],'nextAction':x['nextAction'],'stateHash':continuation.state_hash(v),'schemaVersion':v['schemaVersion']}
def output(v,j):print(json.dumps(v,indent=2 if j else None,ensure_ascii=False))
def main(argv=None):
    args=parser().parse_args(argv);a=GitHubContinuationAuthority()
    try:
        if args.command in {'list','verify','show'}:
            o=a.observe()
            if args.command=='list':p={'schemaVersion':'WorkDiscovery 0.1','authorityBranch':a.authority_branch,'authorityHead':o.head_sha,'items':[summary(v) for _,v in sorted(o.items.items())]}
            elif args.command=='verify':p={'ok':True,'authorityBranch':a.authority_branch,'authorityHead':o.head_sha,'count':len(o.items),'ids':sorted(o.items),'workGraph':work_graph.build([continuation.operational_view(v) for _,v in sorted(o.items.items())])}
            else:
                v=o.items.get(args.id)
                if v is None:raise RuntimeError('CONTINUATION_FILE_MISSING')
                p={'authorityBranch':a.authority_branch,'authorityHead':o.head_sha,'state':v,'stateHash':continuation.state_hash(v)}
            output(p,args.as_json);return 0
        plan=plan_for(a,args);p=a.apply(plan,args.expected_plan) if args.apply else plan;output(p,args.as_json);return 0
    except (RuntimeError,ContinuationRemoteError) as exc:output({'ok':False,'error':getattr(exc,'code',str(exc)),'detail':getattr(exc,'detail','')},getattr(args,'as_json',False));return ERROR_EXIT
if __name__=='__main__':raise SystemExit(main())
