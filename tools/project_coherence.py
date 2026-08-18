#!/usr/bin/env python3
"""Pure cross-authority coherence for ProjectMachineInspection."""
from __future__ import annotations
import json
from tools import work_graph
from tools.semantics.branches import parse_branch_name
from tools.semantics.observation import ObservationStatus

AUTHORITY_IDS={"projectState":"project-state","publication":"publication","git":"git-worktree","repository":"repository","control":"control","capabilities":"capabilities","pullRequests":"github-pull-requests","coordination":"coordination","continuations":"continuations"}

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
    if identity.get("grammar")=="canonical" and identity.get("declaredClass") not in {"work","experiment"}:return None
    return identity.get("semanticDomain")
def _pull_request_items(sensors):
    data=_data(sensors,"pullRequests");available=data.get("available") is True;items=data.get("items") if isinstance(data.get("items"),list) else [];return available,[i for i in items if isinstance(i,dict)]
def _work_bindings(sensors):
    data=_data(sensors,"continuations")
    if data.get("available") is not True:return False,[]
    items=data.get("items") if isinstance(data.get("items"),list) else []
    return True,work_graph.active_execution_bindings([i for i in items if isinstance(i,dict)])
def classify_open_pr(project,pr,bindings):
    number=pr.get("number");head=pr.get("headRef")
    if isinstance(number,int) and any(binding.get("prNumber")==number for binding in bindings):return "work-bound"
    protected=project.get("protectedBranches") or []
    if isinstance(head,str) and head in set(protected):return "protected"
    if _branch_semantic_domain(head)=="operations":return "operations"
    return "unclassified"
def _pr_classification_check(project,sensors,scope):
    required=scope=="live";available,prs=_pull_request_items(sensors)
    if not available:return coherence_check("pull-requests.classification","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["github-pull-requests"],required=required)
    work_available,bindings=_work_bindings(sensors)
    items=[{"number":i.get("number"),"headRef":i.get("headRef"),"classification":classify_open_pr(project,i,bindings)} for i in prs];unclassified=[i for i in items if i["classification"]=="unclassified"]
    if unclassified and not work_available:return coherence_check("pull-requests.classification","UNKNOWN","WORK_AUTHORITY_UNAVAILABLE_FOR_PR_CLASSIFICATION",["continuations","github-pull-requests"],required=required,detail={"items":items,"unclassified":unclassified})
    if unclassified:return coherence_check("pull-requests.classification","FAIL","UNCLASSIFIED_OPEN_PR",["continuations","github-pull-requests"],required=required,detail={"items":items,"unclassified":unclassified})
    return coherence_check("pull-requests.classification","PASS","OPEN_PRS_CLASSIFIED",["continuations","github-pull-requests"],required=required,detail={"items":items})
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
def _work_pr_checks(project,sensors,scope):
    required=scope=="live";work_available,bindings=_work_bindings(sensors)
    if not work_available:
        return [coherence_check("work.pr.open","UNKNOWN","WORK_AUTHORITY_UNAVAILABLE",["continuations","github-pull-requests"],required=required),coherence_check("work.pr.head","UNKNOWN","WORK_IDENTITY_NOT_OBSERVABLE",["continuations","github-pull-requests"],required=False),coherence_check("work.pr.base","UNKNOWN","WORK_IDENTITY_NOT_OBSERVABLE",["continuations","github-pull-requests"],required=False)]
    linked=[item for item in bindings if isinstance(item.get("prNumber"),int)]
    if not linked:
        return [coherence_check("work.pr.open","PASS","NO_ACTIVE_PR_LINKED_WORK",["continuations","github-pull-requests"],required=required,detail={"checked":0}),coherence_check("work.pr.head","PASS","NOT_APPLICABLE",["continuations","github-pull-requests"],required=False),coherence_check("work.pr.base","PASS","NOT_APPLICABLE",["continuations","github-pull-requests"],required=False)]
    pr_available,prs=_pull_request_items(sensors)
    if not pr_available:
        return [coherence_check("work.pr.open","UNKNOWN","REMOTE_PR_INVENTORY_UNAVAILABLE",["continuations","github-pull-requests"],required=required,detail={"checked":len(linked)}),coherence_check("work.pr.head","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["continuations","github-pull-requests"],required=False),coherence_check("work.pr.base","UNKNOWN","PR_IDENTITY_NOT_OBSERVABLE",["continuations","github-pull-requests"],required=False)]
    by_number={i.get("number"):i for i in prs if isinstance(i.get("number"),int)};missing=[];head_mismatch=[];base_mismatch=[];control=project.get("controlBranch")
    for item in linked:
        prn=item["prNumber"];pr=by_number.get(prn)
        if pr is None:missing.append({"workId":item.get("workId"),"prNumber":prn});continue
        branch=item.get("branch")
        if isinstance(branch,str) and branch!=pr.get("headRef"):head_mismatch.append({"workId":item.get("workId"),"prNumber":prn,"expected":branch,"observed":pr.get("headRef")})
        if isinstance(control,str) and pr.get("baseRef")!=control:base_mismatch.append({"workId":item.get("workId"),"prNumber":prn,"expected":control,"observed":pr.get("baseRef")})
    open_check=coherence_check("work.pr.open","FAIL" if missing else "PASS","WORK_PR_NOT_OPEN" if missing else "WORK_PRS_OPEN",["continuations","github-pull-requests"],required=required,detail={"checked":len(linked),"missing":missing})
    head_check=coherence_check("work.pr.head","FAIL" if head_mismatch else "PASS","WORK_PR_BRANCH_MISMATCH" if head_mismatch else "WORK_PR_HEADS_MATCH",["continuations","github-pull-requests"],required=required,detail={"branchMismatch":head_mismatch})
    base_check=coherence_check("work.pr.base","FAIL" if base_mismatch else "PASS","WORK_PR_BASE_MISMATCH" if base_mismatch else "WORK_PR_BASES_MATCH",["continuations","github-pull-requests"],required=required,detail={"baseMismatch":base_mismatch})
    return [open_check,head_check,base_check]
def evaluate_coherence(project,sensors,*,scope):
    if scope not in {"local","base","live"}:raise RuntimeError("PROJECT_COHERENCE_SCOPE_INVALID")
    checks=[_pr_classification_check(project,sensors,scope),_lease_pr_check(sensors,scope),*_work_pr_checks(project,sensors,scope)];return aggregate_coherence(checks)
