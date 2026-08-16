#!/usr/bin/env python3
"""Read-only deterministic Scheduler v0 routing plan."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction
ACTIONS={item.value for item in OperationalAction}; ERROR_EXIT=2

def validate_inspection(value:dict[str,Any])->None:
    if not isinstance(value,dict):raise RuntimeError("SCHEDULER_INSPECTION_INVALID")
    if value.get("schemaVersion")!="MaintenanceInspection 0.2":raise RuntimeError("SCHEDULER_INSPECTION_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True:raise RuntimeError("SCHEDULER_INSPECTION_NOT_READ_ONLY")
    supplied=value.get("inspectionHash")
    if not isinstance(supplied,str) or supplied!=stable_hash({k:v for k,v in value.items() if k!="inspectionHash"}):raise RuntimeError("SCHEDULER_INSPECTION_HASH_MISMATCH")
    rec=value.get("recommendation")
    if not isinstance(rec,dict) or rec.get("action") not in ACTIONS:raise RuntimeError("SCHEDULER_RECOMMENDATION_INVALID")
    if rec.get("decisionScope")!="operational-only" or rec.get("semanticAuthority") is not False:raise RuntimeError("SCHEDULER_SEMANTIC_AUTHORITY_INVALID")
def continuation_for(value,cid):
    for item in value.get("continuations") or []:
        if isinstance(item,dict) and item.get("id")==cid:return item
    raise RuntimeError("SCHEDULER_CONTINUATION_NOT_FOUND")
def continuation_focus(focus):return focus.split(":",1)[1] if isinstance(focus,str) and focus.startswith("continuation:") and len(focus.split(":",1)[1])>0 else None
def route(value):
    rec=value["recommendation"];action=OperationalAction.parse(rec["action"]).value;focus=rec.get("focus");cid=continuation_focus(focus)
    if action==OperationalAction.HANDOFF.value:
        if cid is None:raise RuntimeError("SCHEDULER_HANDOFF_REQUIRES_CONTINUATION")
        item=continuation_for(value,cid)
        if item.get("status")!="HANDOFF" or not isinstance(item.get("handoffTo"),str) or not item["handoffTo"].strip():raise RuntimeError("SCHEDULER_HANDOFF_TARGET_INVALID")
        return {"shouldWake":True,"channelClass":"worker","target":item["handoffTo"],"continuationId":cid}
    if action==OperationalAction.CONTINUE.value:
        if cid is not None:
            item=continuation_for(value,cid)
            if item.get("status") not in {"READY","IN_PROGRESS"} or not isinstance(item.get("actor"),str) or not item["actor"].strip():raise RuntimeError("SCHEDULER_CONTINUE_TARGET_INVALID")
            return {"shouldWake":True,"channelClass":"worker","target":item["actor"],"continuationId":cid}
        return {"shouldWake":True,"channelClass":"supervisor","target":"gitops-supervisor","continuationId":None}
    if action==OperationalAction.RECONCILE.value:return {"shouldWake":True,"channelClass":"supervisor","target":"gitops-supervisor","continuationId":cid}
    if action==OperationalAction.PAUSE.value:return {"shouldWake":False,"channelClass":"none","target":None,"continuationId":cid}
    if action==OperationalAction.NEEDS_HUMAN.value:return {"shouldWake":True,"channelClass":"human","target":"human","continuationId":cid}
    raise RuntimeError("SCHEDULER_ACTION_INVALID")
def build_plan(value):
    validate_inspection(value);rec=value["recommendation"];body={"schemaVersion":"SchedulerPlan 0.1","inspectionHash":value["inspectionHash"],"action":rec["action"],"reasonCode":str(rec.get("reasonCode") or "UNKNOWN"),"focus":rec.get("focus"),"dispatch":route(value),"decisionScope":"operational-only","semanticAuthority":False,"transportSideEffects":False,"readOnly":True};return {**body,"planHash":stable_hash(body)}
def load_json(path):
    try:value=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise RuntimeError("SCHEDULER_INPUT_INVALID") from exc
    if not isinstance(value,dict):raise RuntimeError("SCHEDULER_INPUT_INVALID")
    return value
def live_inspection():
    from tools import maintenance_live
    return maintenance_live.inspect()
def main(argv=None):
    p=argparse.ArgumentParser(prog="scheduler-plan",description="Read-only Scheduler v0 plan");group=p.add_mutually_exclusive_group(required=True);group.add_argument("--input");group.add_argument("--live",action="store_true");p.add_argument("--json",action="store_true",dest="as_json");args=p.parse_args(argv)
    try:value=live_inspection() if args.live else load_json(args.input);payload=build_plan(value);print(json.dumps(payload,indent=2 if args.as_json else None,ensure_ascii=False));return 0
    except RuntimeError as exc:print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False));return ERROR_EXIT
if __name__=="__main__":raise SystemExit(main())
