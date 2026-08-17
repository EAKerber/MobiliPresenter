#!/usr/bin/env python3
"""Bounded live lifecycle probe for the Work authority."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import continuation_transition as transition,maintenance_inspect,project_machine
from tools.continuation_remote import ContinuationRemoteError,GitHubContinuationAuthority
PROBE_ID='work-lifecycle-probe'

def inspect_supervisor():return maintenance_inspect.from_project_inspection(project_machine.inspect_live())
def apply(a,p):return a.apply(p,p['planHash'])
def settle(a,cid,current):
    if current['status']=='HANDOFF':apply(a,transition.resume(current,current['handoffToWorkerId']));current=a.observe().items[cid]
    elif current['status']=='WAITING':apply(a,transition.resume(current,current['workerId']));current=a.observe().items[cid]
    if current['status'] in {'READY','IN_PROGRESS'}:
        if current['remaining']:
            apply(a,transition.advance(current,list(current['remaining']),checkpoint='probe-recovery',inventory=list(a.observe().items.values())));current=a.observe().items[cid]
        apply(a,transition.done(current,inventory=list(a.observe().items.values())))

def main():
    a=GitHubContinuationAuthority();initial=a.observe();initial_count=len(initial.items);current=initial.items.get(PROBE_ID)
    if current is None:apply(a,transition.create(PROBE_ID,'probe-ui',['probe'],'handoff probe'))
    else:
        if current['status']!='DONE':settle(a,PROBE_ID,current);current=a.observe().items[PROBE_ID]
        apply(a,transition.restart(current,['probe'],'handoff probe'))
    ready=a.observe().items[PROBE_ID];stale=transition.wait(ready,['stale-plan-probe']);apply(a,transition.handoff(ready,'probe-engine','resume and finish probe'))
    code=None
    try:apply(a,stale)
    except ContinuationRemoteError as exc:code=exc.code
    if code!='CONTINUATION_PLAN_STALE':raise RuntimeError(f'STALE_PLAN_NOT_REJECTED:{code}')
    inspection=inspect_supervisor()
    if inspection['recommendation']['action']!='HANDOFF' or inspection['recommendation']['focus']!=f'work:{PROBE_ID}':raise RuntimeError('MAINTENANCE_HANDOFF_NOT_OBSERVED')
    current=a.observe().items[PROBE_ID];apply(a,transition.resume(current,'probe-engine'));current=a.observe().items[PROBE_ID]
    sha=os.environ.get('GITHUB_SHA');sha=sha if isinstance(sha,str) and len(sha)==40 else None
    apply(a,transition.advance(current,['probe'],sha=sha,checkpoint='probe-finished',inventory=list(a.observe().items.values())));current=a.observe().items[PROBE_ID]
    done=apply(a,transition.done(current,inventory=list(a.observe().items.values())));final_authority=a.observe();final=inspect_supervisor()
    if final['recommendation']['action']=='HANDOFF' and final['recommendation']['focus']==f'work:{PROBE_ID}':raise RuntimeError('PHANTOM_HANDOFF_AFTER_DONE')
    expected_count=initial_count if PROBE_ID in initial.items else initial_count+1
    if len(final_authority.items)!=expected_count:raise RuntimeError('PROBE_INVENTORY_GROWTH_UNEXPECTED')
    payload={'ok':True,'task':PROBE_ID,'initialCount':initial_count,'finalCount':len(final_authority.items),'authorityHead':final_authority.head_sha,'stalePlanRejected':True,'staleError':code,'done':done,'finalStatus':final_authority.items[PROBE_ID]['status']}
    output=os.environ.get('CONTINUATION_PROBE_OUTPUT')
    if output:Path(output).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
