#!/usr/bin/env python3
"""Operational policy over a factual ProjectMachineInspection."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import project_machine
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction
ERROR_EXIT=2
ACTIONS=tuple(item.value for item in OperationalAction)
ACTION_PRIORITY={"CONTINUE":0,"HANDOFF":1,"PAUSE":2,"RECONCILE":3,"NEEDS_HUMAN":4}
def finding(action,code,detail,subject=None):
    try:action=OperationalAction.parse(str(action)).value
    except RuntimeError as exc:raise RuntimeError("MAINTENANCE_ACTION_INVALID") from exc
    value={"action":action,"code":code,"detail":detail}
    if subject is not None:value["subject"]=subject
    return value
def _sensor_focus(name):return {"pullRequests":"github","coordination":"coordination-leases","continuations":"continuations","projectState":"repository","publication":"publication","control":"main"}.get(name,name)
def _coherence_focus(check):
    code=check.get("code");detail=check.get("detail") if isinstance(check.get("detail"),dict) else {}
    if code=="UNCLASSIFIED_OPEN_PR":
        items=detail.get("unclassified") if isinstance(detail.get("unclassified"),list) else []
        if items and isinstance(items[0],dict) and isinstance(items[0].get("number"),int):return f"pr:{items[0]['number']}"
    if isinstance(code,str) and code.startswith("ACTIVE_PR_"):return "development"
    if isinstance(code,str) and code.startswith("LEASE_OWNER_"):return "coordination-leases"
    if isinstance(code,str) and code.startswith("CONTINUATION_"):return "continuations"
    subjects=check.get("subjects") if isinstance(check.get("subjects"),list) else [];return str(subjects[0]) if subjects else None
def _machine_findings(machine_trust=None,machine_coherence=None,machine_sensors=None):
    out=[];sensors=machine_sensors if isinstance(machine_sensors,dict) else {}
    if isinstance(machine_trust,dict):
        status=str(machine_trust.get("status") or "UNKNOWN").upper();names=machine_trust.get("failedSensors") if status=="FAIL" else machine_trust.get("unknownSensors");action="RECONCILE" if status=="FAIL" else ("NEEDS_HUMAN" if status=="UNKNOWN" else None)
        if action:
            for name in names or ["project-machine"]:
                sensor=sensors.get(name) if isinstance(sensors.get(name),dict) else {};code=sensor.get("code") or ("PROJECT_MACHINE_FAILED" if status=="FAIL" else "PROJECT_MACHINE_INCOMPLETE");out.append(finding(action,str(code),f"factual sensor {name} status is {status}",_sensor_focus(str(name))))
    if isinstance(machine_coherence,dict):
        for check in machine_coherence.get("checks") or []:
            if not isinstance(check,dict) or check.get("required") is not True:continue
            status=str(check.get("status") or "UNKNOWN").upper()
            if status not in {"FAIL","UNKNOWN"}:continue
            action="RECONCILE" if status=="FAIL" else "NEEDS_HUMAN";detail=check.get("detail");rendered=json.dumps(detail,sort_keys=True,ensure_ascii=False) if detail is not None else str(check.get("id"));out.append(finding(action,str(check.get("code") or "PROJECT_COHERENCE_UNKNOWN"),rendered,_coherence_focus(check)))
    return out
def decide(state,verification,capabilities,*,remote_requested,pull_requests,coordination_state,continuations=None,machine_trust=None,machine_coherence=None,machine_sensors=None):
    findings=_machine_findings(machine_trust,machine_coherence,machine_sensors);continuations=continuations or []
    if not verification.get("ok"):
        failed=[i.get("name") for i in verification.get("checks",[]) if i.get("status")=="FAIL"];findings.append(finding("RECONCILE","VERIFICATION_FAILED",f"failed checks: {', '.join(str(i) for i in failed)}","repository"))
    blockers=state["development"].get("blockers") or []
    if blockers:findings.append(finding("PAUSE","EXPLICIT_BLOCKERS","; ".join(str(i) for i in blockers),"development"))
    for task in continuations:
        subject=f"continuation:{task['id']}";status=task["status"]
        if status=="HANDOFF":findings.append(finding("HANDOFF","CONTINUATION_HANDOFF_REQUIRED",f"handoff to {task['handoffTo']}: {task['nextAction']}",subject))
        elif status=="WAITING":findings.append(finding("PAUSE","CONTINUATION_WAITING","; ".join(task["blockedBy"]),subject))
        elif status in {"READY","IN_PROGRESS"}:findings.append(finding("CONTINUE","CONTINUATION_RUNNABLE",task["nextAction"] or "finish and mark done",subject))
    for item in capabilities:
        if item["policy"]!="experimental" or item.get("supervisorParticipation","active")=="isolated":continue
        if item["reviewAction"]=="REVIEW_EMPTY_LIMIT":findings.append(finding("NEEDS_HUMAN","CAPABILITY_EMPTY_LIMIT","formal capability review reached its configured empty-round limit",item["id"]))
        elif item["reviewAction"]=="TEST_NEXT_GATES":findings.append(finding("CONTINUE","CAPABILITY_GATES_DUE",f"next Gates: {', '.join(item['nextGates'])}",item["id"]))
        elif item["reviewAction"]=="REVIEW_EMPTY_ROUND":findings.append(finding("CONTINUE","CAPABILITY_EMPTY_REVIEW_DUE","re-evaluate the recorded deferral reason",item["id"]))
    if remote_requested and pull_requests.get("available"):
        active_pr=state["development"].get("prNumber")
        if isinstance(active_pr,int):
            matches=[i for i in pull_requests.get("items",[]) if i.get("number")==active_pr]
            if matches:
                ci=str(matches[0].get("ci") or "unknown");observed=matches[0].get("ciObserved") is True
                if ci=="failed":findings.append(finding("RECONCILE","ACTIVE_PR_CI_FAILED",f"PR #{active_pr} CI is failed",f"pr:{active_pr}"))
                elif ci=="pending":findings.append(finding("PAUSE","ACTIVE_PR_CI_PENDING",f"PR #{active_pr} CI is pending",f"pr:{active_pr}"))
                elif ci=="unknown" or not observed:findings.append(finding("NEEDS_HUMAN","ACTIVE_PR_CI_UNKNOWN",f"PR #{active_pr} CI could not be established",f"pr:{active_pr}"))
    if not findings:findings.append(finding("CONTINUE","NEXT_TRANSITION_AVAILABLE",state["development"]["nextTransition"],"development"))
    indexed=list(enumerate(findings));_,best=max(indexed,key=lambda p:(ACTION_PRIORITY[p[1]["action"]],-p[0]));recommendation={"action":best["action"],"reasonCode":best["code"],"focus":best.get("subject"),"detail":best["detail"],"decisionScope":"operational-only","semanticAuthority":False,"allowedActions":list(ACTIONS)};return findings,recommendation
def build_inspection(state,verification,observed_git,capabilities,*,remote_requested,pull_requests,coordination_state,continuations=None,machine_trust=None,machine_coherence=None,machine_sensors=None):
    continuations=continuations or [];findings,recommendation=decide(state,verification,capabilities,remote_requested=remote_requested,pull_requests=pull_requests,coordination_state=coordination_state,continuations=continuations,machine_trust=machine_trust,machine_coherence=machine_coherence,machine_sensors=machine_sensors);body={"schemaVersion":"MaintenanceInspection 0.2","repository":state["project"]["repository"],"projectState":{"phase":state["development"]["phase"],"checkpoint":state["development"]["checkpoint"],"nextTransition":state["development"]["nextTransition"],"activeDevelopmentBranch":state["git"].get("activeDevelopmentBranch"),"developmentPrNumber":state["development"].get("prNumber"),"blockers":state["development"].get("blockers") or []},"verification":verification,"observedGit":observed_git,"capabilities":capabilities,"continuations":continuations,"remoteRequested":remote_requested,"pullRequests":pull_requests,"coordination":coordination_state,"findings":findings,"recommendation":recommendation,"readOnly":True};return {**body,"inspectionHash":stable_hash(body)}
def _sensor_data(machine,name):
    sensors=machine.get("sensors")
    if not isinstance(sensors,dict) or not isinstance(sensors.get(name),dict):raise RuntimeError(f"PROJECT_MACHINE_SENSOR_MISSING:{name}")
    data=sensors[name].get("data")
    if not isinstance(data,dict):raise RuntimeError(f"PROJECT_MACHINE_SENSOR_DATA_INVALID:{name}")
    return data
def from_project_inspection(machine):
    project_machine.validate_inspection(machine);project=machine["project"];state={"project":{"repository":machine["repository"]},"git":{"activeDevelopmentBranch":project.get("activeDevelopmentBranch"),"controlBranch":project.get("controlBranch")},"development":{"phase":project["phase"],"checkpoint":project["checkpoint"],"nextTransition":project["nextTransition"],"prNumber":project.get("developmentPrNumber"),"blockers":project.get("blockers") or []}};project_state=_sensor_data(machine,"projectState");git_data=_sensor_data(machine,"git");capability_data=_sensor_data(machine,"capabilities");pull_request_data=_sensor_data(machine,"pullRequests");coordination_data=_sensor_data(machine,"coordination");continuation_data=_sensor_data(machine,"continuations");verification=project_state.get("verification");observed_git=git_data.get("observed")
    if not isinstance(verification,dict):raise RuntimeError("PROJECT_MACHINE_VERIFICATION_INVALID")
    if not isinstance(observed_git,dict):raise RuntimeError("PROJECT_MACHINE_GIT_OBSERVATION_INVALID")
    return build_inspection(state,verification,observed_git,capability_data.get("items") or [],remote_requested=machine["scope"] in {"base","live"},pull_requests=pull_request_data,coordination_state=coordination_data,continuations=continuation_data.get("items") or [],machine_trust=machine.get("trust"),machine_coherence=machine.get("coherence"),machine_sensors=machine.get("sensors"))
def inspect(include_remote):return from_project_inspection(project_machine.inspect_base() if include_remote else project_machine.inspect_local())
def main(argv=None):
    parser=argparse.ArgumentParser(prog="maintenance-inspect");parser.add_argument("--json",action="store_true",dest="as_json");parser.add_argument("--remote",action="store_true");args=parser.parse_args(argv)
    try:
        payload=inspect(args.remote);print(json.dumps(payload,indent=2,ensure_ascii=False) if args.as_json else "MAINTENANCE INSPECT\n  recommendation: %s\n  reason: %s\n  focus: %s\n  continuations: %d\n  inspectionHash: %s"%(payload["recommendation"]["action"],payload["recommendation"]["reasonCode"],payload["recommendation"].get("focus") or "(none)",len(payload["continuations"]),payload["inspectionHash"]));return 0
    except RuntimeError as exc:print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}");return ERROR_EXIT
if __name__=="__main__":raise SystemExit(main())
