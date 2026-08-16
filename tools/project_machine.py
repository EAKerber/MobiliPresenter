#!/usr/bin/env python3
"""Compose and validate a read-only factual inspection of MobiliPresenter."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import project_coherence,project_sensors,project_state,work_graph
from tools.canonical import stable_hash
from tools.semantics.observation import ObservationStatus
SCHEMA_VERSION="ProjectMachineInspection 0.4";REPOSITORY="EAKerber/MobiliPresenter";SCOPES={"local","base","live"};ERROR_EXIT=2;UNKNOWN_EXIT=1

def _sensor_status(value):
    if not isinstance(value,dict):return ObservationStatus.FAIL.value
    try:return ObservationStatus.parse(str(value.get("status") or ObservationStatus.UNKNOWN.value).upper()).value
    except RuntimeError:return ObservationStatus.FAIL.value

def aggregate_trust(sensors):
    failed=[];unknown=[]
    for name,value in sensors.items():
        if value.get("required") is not True:continue
        status=_sensor_status(value)
        if status==ObservationStatus.FAIL.value:failed.append(name)
        elif status==ObservationStatus.UNKNOWN.value:unknown.append(name)
    status=ObservationStatus.FAIL.value if failed else (ObservationStatus.UNKNOWN.value if unknown else ObservationStatus.PASS.value)
    return {"status":status,"ok":status!=ObservationStatus.FAIL.value,"complete":status==ObservationStatus.PASS.value,"failedSensors":sorted(failed),"unknownSensors":sorted(unknown)}

def source_heads(sensors):
    git_data=sensors.get("git",{}).get("data") or {};observed=git_data.get("observed") if isinstance(git_data,dict) else {};control=sensors.get("control",{}).get("data") or {};coordination=sensors.get("coordination",{}).get("data") or {};continuations=sensors.get("continuations",{}).get("data") or {}
    return {"inspection":{"branch":observed.get("branch") if isinstance(observed,dict) else None,"sha":observed.get("head") if isinstance(observed,dict) else None},"control":{"branch":control.get("branch"),"sha":control.get("sha")},"coordination":{"branch":coordination.get("authorityBranch"),"sha":coordination.get("authorityHead")},"continuation":{"branch":continuations.get("authorityBranch"),"sha":continuations.get("authorityHead")}}

def work_graph_projection(sensors):
    continuation_data=sensors.get("continuations",{}).get("data") or {}
    if not isinstance(continuation_data,dict):raise RuntimeError("PROJECT_MACHINE_WORK_DATA_INVALID")
    raw_items=continuation_data.get("items")
    if not isinstance(raw_items,list):raise RuntimeError("PROJECT_MACHINE_WORK_ITEMS_INVALID")
    if any(not isinstance(item,dict) for item in raw_items):raise RuntimeError("PROJECT_MACHINE_WORK_ITEM_INVALID")
    return work_graph.build(raw_items)

def observations(sensors):
    out=[];continuation_data=sensors.get("continuations",{}).get("data") or {};items=continuation_data.get("items",[]) if isinstance(continuation_data,dict) else [];terminal=[item for item in items if isinstance(item,dict) and item.get("status")=="DONE"]
    if terminal:out.append({"severity":"INFO","code":"TERMINAL_CONTINUATION_RESIDUE","subject":"coordination/continuations","count":len(terminal),"ids":sorted(str(item.get("id")) for item in terminal)})
    return out

def project_summary(state):
    view=project_state.operational_view(state)
    return {"stateHash":stable_hash(state),"controlBranch":view["git"]["controlBranch"],"protectedBranches":sorted(view["git"].get("protectedBranches") or []),"phase":view["development"]["phase"],"checkpoint":view["development"]["checkpoint"],"nextTransition":view["development"]["nextTransition"],"activeDevelopmentBranch":view["git"].get("activeDevelopmentBranch"),"developmentPrNumber":view["development"].get("prNumber"),"blockers":view["development"].get("blockers") or []}

def build_inspection(state,sensors,*,scope):
    if scope not in SCOPES:raise RuntimeError("PROJECT_MACHINE_SCOPE_INVALID")
    view=project_state.operational_view(state);project=project_summary(state);graph=work_graph_projection(sensors);body={"schemaVersion":SCHEMA_VERSION,"repository":view["project"]["repository"],"scope":scope,"sourceHeads":source_heads(sensors),"project":project,"sensors":sensors,"workGraph":graph,"authorities":project_coherence.derive_authorities(sensors),"trust":aggregate_trust(sensors),"coherence":project_coherence.evaluate_coherence(project,sensors,scope=scope),"observations":observations(sensors),"readOnly":True,"semanticAuthority":False};return {**body,"inspectionHash":stable_hash(body)}

def _load_state():
    state=project_state.load_state();errors=project_state.validate_current(state)
    if errors:raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return state

def _common_sensors(state):
    sensors=project_sensors.observe_local_core(state);sensors["capabilities"]=project_sensors.observe_capabilities();return sensors

def inspect_local():
    state=_load_state();sensors=_common_sensors(state);sensors["control"]=project_sensors.observe_control_head(state,live=False);sensors["pullRequests"]=project_sensors.observe_pull_requests(state,live=False);sensors["coordination"]=project_sensors.observe_coordination(live=False);sensors["continuations"]=project_sensors.observe_continuations_local();return build_inspection(state,sensors,scope="local")
def inspect_base():
    state=_load_state();sensors=_common_sensors(state);sensors["control"]=project_sensors.observe_control_head(state,live=True);sensors["pullRequests"]=project_sensors.observe_pull_requests(state,live=True);sensors["coordination"]=project_sensors.observe_coordination(live=True);sensors["continuations"]=project_sensors.observe_continuations_local();return build_inspection(state,sensors,scope="base")
def inspect_live():
    state=_load_state();sensors=_common_sensors(state);sensors["control"]=project_sensors.observe_control_head(state,live=True);sensors["pullRequests"]=project_sensors.observe_pull_requests(state,live=True);sensors["coordination"]=project_sensors.observe_coordination(live=True);sensors["continuations"]=project_sensors.observe_continuations_live();return build_inspection(state,sensors,scope="live")
def _require_sha_or_none(value,code):
    if value is None:return
    if not isinstance(value,str) or len(value)!=40 or any(char not in "0123456789abcdef" for char in value):raise RuntimeError(code)
def validate_inspection(value):
    if not isinstance(value,dict):raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    if value.get("schemaVersion")!=SCHEMA_VERSION:raise RuntimeError("PROJECT_MACHINE_SCHEMA_UNSUPPORTED")
    if value.get("repository")!=REPOSITORY:raise RuntimeError("PROJECT_MACHINE_REPOSITORY_MISMATCH")
    if value.get("scope") not in SCOPES:raise RuntimeError("PROJECT_MACHINE_SCOPE_INVALID")
    if value.get("readOnly") is not True:raise RuntimeError("PROJECT_MACHINE_NOT_READ_ONLY")
    if value.get("semanticAuthority") is not False:raise RuntimeError("PROJECT_MACHINE_SEMANTIC_AUTHORITY_INVALID")
    project=value.get("project")
    if not isinstance(project,dict):raise RuntimeError("PROJECT_MACHINE_PROJECT_INVALID")
    if not isinstance(project.get("controlBranch"),str):raise RuntimeError("PROJECT_MACHINE_CONTROL_BRANCH_INVALID")
    if not isinstance(project.get("protectedBranches"),list):raise RuntimeError("PROJECT_MACHINE_PROTECTED_BRANCHES_INVALID")
    sensors=value.get("sensors")
    if not isinstance(sensors,dict) or not sensors:raise RuntimeError("PROJECT_MACHINE_SENSORS_INVALID")
    for name,item in sensors.items():
        if not isinstance(name,str) or not isinstance(item,dict):raise RuntimeError("PROJECT_MACHINE_SENSOR_INVALID")
        try:ObservationStatus.parse(str(item.get("status") or "").upper())
        except RuntimeError as exc:raise RuntimeError("PROJECT_MACHINE_SENSOR_STATUS_INVALID") from exc
        if not isinstance(item.get("required"),bool):raise RuntimeError("PROJECT_MACHINE_SENSOR_REQUIRED_INVALID")
    expected_graph=work_graph_projection(sensors)
    if value.get("workGraph")!=expected_graph:raise RuntimeError("PROJECT_MACHINE_WORK_GRAPH_MISMATCH")
    expected_authorities=project_coherence.derive_authorities(sensors)
    if value.get("authorities")!=expected_authorities:raise RuntimeError("PROJECT_MACHINE_AUTHORITIES_MISMATCH")
    trust=value.get("trust");expected_trust=aggregate_trust(sensors)
    if trust!=expected_trust:raise RuntimeError("PROJECT_MACHINE_TRUST_MISMATCH")
    expected_coherence=project_coherence.evaluate_coherence(project,sensors,scope=value["scope"])
    if value.get("coherence")!=expected_coherence:raise RuntimeError("PROJECT_MACHINE_COHERENCE_MISMATCH")
    heads=value.get("sourceHeads")
    if not isinstance(heads,dict):raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_INVALID")
    if heads!=source_heads(sensors):raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_MISMATCH")
    for name in ("inspection","control","coordination","continuation"):
        head=heads.get(name)
        if not isinstance(head,dict):raise RuntimeError("PROJECT_MACHINE_SOURCE_HEAD_INVALID")
        _require_sha_or_none(head.get("sha"),f"PROJECT_MACHINE_{name.upper()}_HEAD_INVALID")
    if value.get("observations")!=observations(sensors):raise RuntimeError("PROJECT_MACHINE_OBSERVATIONS_MISMATCH")
    supplied=value.get("inspectionHash");body={key:item for key,item in value.items() if key!="inspectionHash"};expected=stable_hash(body)
    if not isinstance(supplied,str) or supplied!=expected:raise RuntimeError("PROJECT_MACHINE_HASH_MISMATCH")
    return {"ok":True,"inspectionHash":supplied,"trust":trust,"coherence":value["coherence"],"scope":value["scope"],"sourceHeads":heads}
def load_json(path):
    try:value=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID") from exc
    if not isinstance(value,dict):raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    return value
def _print_human(payload):
    trust=payload["trust"];coherence=payload["coherence"];project=payload["project"];graph=payload["workGraph"];print("PROJECT MACHINE INSPECTION");print(f"  scope: {payload['scope']}");print(f"  trust: {trust['status']}");print(f"  coherence: {coherence['status']}");print(f"  phase: {project['phase']}");print(f"  checkpoint: {project['checkpoint']}");print(f"  next: {project['nextTransition']}");print(f"  runnable work: {len(graph['runnable'])}");print(f"  authorities: {len(payload['authorities'])}");print(f"  observations: {len(payload['observations'])}");print(f"  inspectionHash: {payload['inspectionHash']}")
def main(argv=None):
    parser=argparse.ArgumentParser(prog="project-machine");sub=parser.add_subparsers(dest="command",required=True);inspect_parser=sub.add_parser("inspect");scope_group=inspect_parser.add_mutually_exclusive_group(required=True);scope_group.add_argument("--live",action="store_true");scope_group.add_argument("--base",action="store_true");scope_group.add_argument("--local",action="store_true");inspect_parser.add_argument("--json",action="store_true",dest="as_json");validate_parser=sub.add_parser("validate");validate_parser.add_argument("path");validate_parser.add_argument("--json",action="store_true",dest="as_json");args=parser.parse_args(argv)
    try:
        if args.command=="validate":result=validate_inspection(load_json(args.path));print(json.dumps(result,indent=2 if args.as_json else None,ensure_ascii=False));return 0
        payload=inspect_live() if args.live else (inspect_base() if args.base else inspect_local())
        print(json.dumps(payload,indent=2,ensure_ascii=False) if args.as_json else "") if args.as_json else _print_human(payload);status=payload["trust"]["status"];coherence_status=payload["coherence"]["status"]
        if status==ObservationStatus.FAIL.value or coherence_status==ObservationStatus.FAIL.value:return ERROR_EXIT
        if status==ObservationStatus.UNKNOWN.value or coherence_status==ObservationStatus.UNKNOWN.value:return UNKNOWN_EXIT
        return 0
    except RuntimeError as exc:print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if getattr(args,"as_json",False) else f"BLOCKED\n{exc}");return ERROR_EXIT
if __name__=="__main__":raise SystemExit(main())
