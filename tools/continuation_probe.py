#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import continuation_transition as transition, maintenance_inspect, project_machine
from tools.continuation_remote import ContinuationRemoteError,GitHubContinuationAuthority

def inspect_supervisor():
    machine=project_machine.inspect_live()
    return maintenance_inspect.from_project_inspection(machine)

def finish_probe(a,cid,value):
    current=value
    if current["status"]=="HANDOFF":
        p=transition.resume(current,current["handoffTo"]); a.apply(p,p["planHash"]); current=a.observe().items[cid]
    elif current["status"]=="WAITING":
        p=transition.resume(current,current["actor"]); a.apply(p,p["planHash"]); current=a.observe().items[cid]
    if current["status"] in {"READY","IN_PROGRESS"}:
        if current["remaining"]:
            p=transition.advance(current,list(current["remaining"]),checkpoint="probe-cleanup"); a.apply(p,p["planHash"]); current=a.observe().items[cid]
        p=transition.done(current); a.apply(p,p["planHash"])

def main():
    task=f"probe-continuation-{os.environ.get('GITHUB_RUN_ID','local')}"; a=GitHubContinuationAuthority(); initial=a.observe()
    for cid,value in list(initial.items.items()):
        if cid.startswith("probe-continuation-") and cid!=task and value["status"]!="DONE": finish_probe(a,cid,value)
    initial=a.observe()
    if task in initial.items: raise RuntimeError("PROBE_TASK_ALREADY_EXISTS")
    p=transition.create(task,"probe-ui",["probe"],"handoff probe"); created=a.apply(p,p["planHash"]); ready=a.observe().items[task]
    stale=transition.wait(ready,["stale-plan-probe"]); p=transition.handoff(ready,"probe-engine","resume and finish probe"); handed=a.apply(p,p["planHash"])
    code=None
    try:a.apply(stale,stale["planHash"])
    except ContinuationRemoteError as exc:code=exc.code
    if code!="CONTINUATION_PLAN_STALE":raise RuntimeError(f"STALE_PLAN_NOT_REJECTED:{code}")
    inspection=inspect_supervisor()
    if inspection["recommendation"]["action"]!="HANDOFF" or inspection["recommendation"]["focus"]!=f"work:{task}":raise RuntimeError("MAINTENANCE_HANDOFF_NOT_OBSERVED")
    current=a.observe().items[task];p=transition.resume(current,"probe-engine");resumed=a.apply(p,p["planHash"])
    current=a.observe().items[task];sha=os.environ.get("GITHUB_SHA");sha=sha if isinstance(sha,str) and len(sha)==40 else None;p=transition.advance(current,["probe"],sha=sha,checkpoint="probe-finished");advanced=a.apply(p,p["planHash"])
    current=a.observe().items[task];p=transition.done(current);done=a.apply(p,p["planHash"]);final=inspect_supervisor()
    if final["recommendation"]["action"]=="HANDOFF" and final["recommendation"]["focus"]==f"work:{task}":raise RuntimeError("PHANTOM_HANDOFF_AFTER_DONE")
    payload={"ok":True,"task":task,"initialAuthorityHead":initial.head_sha,"create":created,"handoff":handed,"stalePlanRejected":True,"staleError":code,"handoffInspection":{"action":inspection["recommendation"]["action"],"focus":inspection["recommendation"]["focus"],"inspectionHash":inspection["inspectionHash"]},"resume":resumed,"advance":advanced,"done":done,"finalInspection":{"action":final["recommendation"]["action"],"focus":final["recommendation"]["focus"],"inspectionHash":final["inspectionHash"]}}
    output=os.environ.get("CONTINUATION_PROBE_OUTPUT")
    if output:Path(output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
