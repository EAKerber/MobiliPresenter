#!/usr/bin/env python3
"""Pure cross-authority coherence for ProjectMachineInspection."""
from __future__ import annotations

import json
from typing import Any

from tools.semantics.branches import parse_branch_name
from tools.semantics.observation import ObservationStatus

AUTHORITY_IDS={"projectState":"project-state","publication":"publication","git":"git-worktree","repository":"repository","control":"control","capabilities":"capabilities","pullRequests":"github-pull-requests","coordination":"coordination","continuations":"continuations"}


def _status(sensor):
    if not isinstance(sensor,dict):return ObservationStatus.FAIL.value
    try:return ObservationStatus.parse(str(sensor.get("status") or ObservationStatus.UNKNOWN.value).upper()).value
    except RuntimeError:return ObservationStatus.FAIL.value

def _data(sensors,name):
    sensor=sensors.get(name);data=sensor.get("data") if isinstance(sensor,dict) else None;return data if isinstance(data,dict) else {}

def derive_authorities(sensors):
    grouped={}
    for sensor_name in sorted(sensors):
        sensor=sensors[sensor_name];authority=sensor.get("authority") if isinstance(sensor,dict) else None
        if not isinstance(authority,dict) or not authority:continue
        key=json.dumps(authority,sort_keys=True,separators=(",",":"),ensure_ascii=False);grouped.setdefault(key,{"authority":authority,"observedBy":[]})["observedBy"].append(sensor_name)
    out=[]
    for key in sorted(grouped):
        group=grouped[key];observed_by=sorted(group["observedBy"]);authority=group["authority"];preferred=next((AUTHORITY_IDS[n] for n in observed_by if n in AUTHORITY_IDS),observed_by[0]);out.append({"id":preferred,"kind":authority.get("kind"),"locator":{n:authority[n] for n in sorted(authority) if n!="kind"},"observedBy":observed_by})
    out.sort(key=lambda item:(str(item["id"]),json.dumps(item["locator"],sort_keys=True)));return out

def coherence_check(check_id,status,code,subjects,*,required=True,detail=None):
    try:normalized=ObservationStatus.parse(str(status).upper()).value
    except RuntimeError as exc:raise RuntimeError("PROJECT_COHERENCE_STATUS_INVALID") from exc
    return {"id":check_id,"status":normalized,"required":bool(required),"code":code,"subjects":list(subjects),"detail":detail}

def aggregate_coherence(checks):
    failed=sorted(i["id"] for i in checks if i.get("required") is True and i.get("status")==ObservationStatus.FAIL.value);unknown=sorted(i["id"] for i in checks if i.get("required") is True and i.get("status")==ObservationStatus.UNKNOWN.value);status=ObservationStatus.FAIL.value if failed else (ObservationStatus.UNKNOWN.value if unknown else ObservationStatus.PASS.value);return {"status":status,"ok":status!=ObservationStatus.FAIL.value,"complete":status==ObservationStatus.PASS.value,"failedChecks":failed,"unknownChecks":unknown,"checks":checks}

def _branch_semantic_domain(head):
    if not isinstance(head,str):return None
    try:identity=parse_branch_name(head)
    except RuntimeError:return None
    if identity.get("grammar") == "canonical" and identity.get("declaredClass") not in {"work","experiment"}:return None
    return identity.get("semanticDomain")

def classify_open_pr(project,pr):
    number=pr.get("number");head=pr.get("headRef")
    if isinstance(number,int) and number==project.get("developmentPrNumber") and isinstance(head,str) and head==project.get("activeDevelopmentBranch"):return "active-development"
    preserve=project.get("preserveBranches") or []
    if isinstance(head,str) and head in set(preserve):return "preserved"
    if _branch_semantic_domain(head)=="operations":return "operations"
    return "unclassified"

def _pull_request_items(sensors):
    data=_data(sensors,"pullRequests");available=data.get("available") is True;items=data.get("items") if isinstance(data.get("items"),list) else [];return available,[i for i in items if isinstance(i,dict)]

def _development_checks(project,sensors,scope):
    active=project.get("activeDevelopmentBranch");pr_number=project.get("developmentPrNumber");remote_required=scope in {"base","live"};checks=[]
    if active is None and pr_number is None:
        checks.append(coherence_check("development.identity.complete","PASS","NO_ACTIVE_DEVELOPMENT",["project-state"],detail=None))
        for cid in ("development.pr.open","development.pr.head","development.pr.base"):checks.append(coherence_check(cid,"PASS","NOT_APPLICABLE",["project-state","github-pull-requests"],required=False))
        return checks
    if (active is None)!=(pr_number is None):
        checks.append(coherence_check("development.identity.complete","FAIL","DEVELOPMENT_IDENTITY_INCOMPLETE",["project-state"],detail={"activeDevelopmentBranch":active,"developmentPrNumber":pr_number}))
        for cid in ("development.pr.open","development.pr.head","development.pr.base"):checks.append(coherence_check(cid,"PASS","NOT_APPLICABLE",["project-state","github-pull-requests"],required=False))
        return checks
    checks.append(coherence_check("development.identity.complete","PASS","DEVELOPMENT_IDENTITY_COMPLETE",["project-state"]))
    if not remote_required:
        for cid in ("development.pr.open","development.pr.head","development.pr.base"):checks.append(coherence_check(cid,"UNKNOWN","NOT_OBSERVED_IN_LOCAL_SCOPE",["project-state","github-pull-requests"],required=False))
        return checks
    available,prs=_pull_request_items(sensors)
    if not available:
        checks.append(coherence_check("development.pr.open","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["project-state","github-pull-requests"]));checks.append(coherence_check("development.pr.head","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["project-state","github-pull-requests"],required=False));checks.append(coherence_check("development.pr.base","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["project-state","github-pull-requests"],required=False));return checks
    matches=[i for i in prs if i.get("number")==pr_number]
    if not matches:
        checks.append(coherence_check("development.pr.open","FAIL","ACTIVE_PR_NOT_OPEN",["project-state","github-pull-requests"],detail={"prNumber":pr_number}));checks.append(coherence_check("development.pr.head","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["project-state","github-pull-requests"],required=False));checks.append(coherence_check("development.pr.base","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["project-state","github-pull-requests"],required=False));return checks
    pr=matches[0];checks.append(coherence_check("development.pr.open","PASS","ACTIVE_PR_OPEN",["project-state","github-pull-requests"],detail={"prNumber":pr_number}));checks.append(coherence_check("development.pr.head","FAIL" if pr.get("headRef")!=active else "PASS","ACTIVE_PR_HEAD_MISMATCH" if pr.get("headRef")!=active else "ACTIVE_PR_HEAD_MATCH",["project-state","github-pull-requests"],detail={"expected":active,"observed":pr.get("headRef"),"prNumber":pr_number} if pr.get("headRef")!=active else {"prNumber":pr_number}));control=project.get("controlBranch");checks.append(coherence_check("development.pr.base","FAIL" if pr.get("baseRef")!=control else "PASS","ACTIVE_PR_BASE_MISMATCH" if pr.get("baseRef")!=control else "ACTIVE_PR_BASE_MATCH",["project-state","github-pull-requests"],detail={"expected":control,"observed":pr.get("baseRef"),"prNumber":pr_number} if pr.get("baseRef")!=control else {"prNumber":pr_number}));return checks

def _pr_classification_check(project,sensors,scope):
    required=scope in {"base","live"};available,prs=_pull_request_items(sensors)
    if not available:return coherence_check("pull-requests.classification","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["project-state","github-pull-requests"],required=required)
    items=[{"number":i.get("number"),"headRef":i.get("headRef"),"classification":classify_open_pr(project,i)} for i in prs];unclassified=[i for i in items if i["classification"]=="unclassified"]
    if unclassified:return coherence_check("pull-requests.classification","FAIL","UNCLASSIFIED_OPEN_PR",["project-state","github-pull-requests"],required=required,detail={"items":items,"unclassified":unclassified})
    return coherence_check("pull-requests.classification","PASS","OPEN_PRS_CLASSIFIED",["project-state","github-pull-requests"],required=required,detail={"items":items})

def _lease_pr_check(sensors,scope):
    required=scope in {"base","live"};coordination=_data(sensors,"coordination")
    if coordination.get("available") is not True:return coherence_check("coordination.lease.pr","UNKNOWN","COORDINATION_AUTHORITY_UNAVAILABLE",["coordination","github-pull-requests"],required=required)
    leases=coordination.get("leases") if isinstance(coordination.get("leases"),list) else [];linked=[]
    for lease in leases:
        owner=lease.get("owner") if isinstance(lease,dict) and isinstance(lease.get("owner"),dict) else {}
        if isinstance(owner.get("pr"),int):linked.append((lease,owner))
    if not linked:return coherence_check("coordination.lease.pr","PASS","NO_PR_LINKED_LEASES",["coordination","github-pull-requests"],required=required,detail={"checked":0})
    available,prs=_pull_request_items(sensors)
    if not available:return coherence_check("coordination.lease.pr","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["coordination","github-pull-requests"],required=required,detail={"checked":len(linked)})
    by_number={i.get("number"):i for i in prs if isinstance(i.get("number"),int)};missing=[];mismatch=[]
    for lease,owner in linked:
        prn=owner["pr"];pr=by_number.get(prn)
        if pr is None:missing.append({"leaseId":lease.get("leaseId"),"prNumber":prn});continue
        branch=owner.get("branch")
        if isinstance(branch,str) and branch!=pr.get("headRef"):mismatch.append({"leaseId":lease.get("leaseId"),"prNumber":prn,"expected":branch,"observed":pr.get("headRef")})
    if missing:return coherence_check("coordination.lease.pr","FAIL","LEASE_OWNER_PR_NOT_OPEN",["coordination","github-pull-requests"],required=required,detail={"missing":missing,"branchMismatch":mismatch})
    if mismatch:return coherence_check("coordination.lease.pr","FAIL","LEASE_OWNER_BRANCH_MISMATCH",["coordination","github-pull-requests"],required=required,detail={"branchMismatch":mismatch})
    return coherence_check("coordination.lease.pr","PASS","LEASE_PR_RELATIONS_COHERENT",["coordination","github-pull-requests"],required=required,detail={"checked":len(linked)})

def _continuation_pr_check(sensors,scope):
    required=scope=="live";continuations=_data(sensors,"continuations")
    if continuations.get("available") is not True:return coherence_check("continuations.pr","UNKNOWN","CONTINUATION_AUTHORITY_UNAVAILABLE",["continuations","github-pull-requests"],required=required)
    items=continuations.get("items") if isinstance(continuations.get("items"),list) else [];linked=[i for i in items if isinstance(i,dict) and i.get("status")!="DONE" and isinstance(i.get("prNumber"),int)]
    if not linked:return coherence_check("continuations.pr","PASS","NO_ACTIVE_PR_LINKED_CONTINUATIONS",["continuations","github-pull-requests"],required=required,detail={"checked":0})
    available,prs=_pull_request_items(sensors)
    if not available:return coherence_check("continuations.pr","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["continuations","github-pull-requests"],required=required,detail={"checked":len(linked)})
    by_number={i.get("number"):i for i in prs if isinstance(i.get("number"),int)};missing=[];mismatch=[]
    for item in linked:
        prn=item["prNumber"];pr=by_number.get(prn)
        if pr is None:missing.append({"continuationId":item.get("id"),"prNumber":prn});continue
        branch=item.get("branch")
        if isinstance(branch,str) and branch!=pr.get("headRef"):mismatch.append({"continuationId":item.get("id"),"prNumber":prn,"expected":branch,"observed":pr.get("headRef")})
    if missing:return coherence_check("continuations.pr","FAIL","CONTINUATION_PR_NOT_OPEN",["continuations","github-pull-requests"],required=required,detail={"missing":missing,"branchMismatch":mismatch})
    if mismatch:return coherence_check("continuations.pr","FAIL","CONTINUATION_PR_BRANCH_MISMATCH",["continuations","github-pull-requests"],required=required,detail={"branchMismatch":mismatch})
    return coherence_check("continuations.pr","PASS","CONTINUATION_PR_RELATIONS_COHERENT",["continuations","github-pull-requests"],required=required,detail={"checked":len(linked)})

def evaluate_coherence(project,sensors,*,scope):
    if scope not in {"local","base","live"}:raise RuntimeError("PROJECT_COHERENCE_SCOPE_INVALID")
    checks=_development_checks(project,sensors,scope);checks.append(_pr_classification_check(project,sensors,scope));checks.append(_lease_pr_check(sensors,scope));checks.append(_continuation_pr_check(sensors,scope));return aggregate_coherence(checks)
