"""Pure WorkItem / ContinuationState 0.2 planners using Transition Protocol 0.1."""
from __future__ import annotations

import copy
import re
from typing import Any

from tools import continuation, transition_protocol as protocol, work_graph
from tools.semantics.work import WorkStatus

DEFAULT_REPOSITORY = "EAKerber/MobiliPresenter"
DEFAULT_BRANCH = "coordination/continuations"
DEFAULT_DIR = "ops/continuations"


def _authority(repository: str = DEFAULT_REPOSITORY, branch: str = DEFAULT_BRANCH, state_dir: str = DEFAULT_DIR) -> dict[str, Any]:
    return {"kind": "git-authority", "locator": {"repository": repository, "branch": branch, "path": state_dir}}


def _build(action: str, before: dict[str, Any] | None, after: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    if before is not None:
        continuation.valid(before, after["id"])
    continuation.valid(after, after["id"])
    return protocol.build_plan(domain="continuation", action=action, subject={"kind": "continuation", "id": after["id"]}, authority=_authority(), before=before, candidate=after, intent=intent, reversibility="revertible")


def create(cid: str, worker_id: str, remaining: list[str], next_action: str, branch: str | None = None, pr: int | None = None, *, depends_on: list[str] | None = None) -> dict[str, Any]:
    if not continuation.ID_RE.fullmatch(cid): raise RuntimeError("CONTINUATION_ID_INVALID")
    worker_id=continuation._worker(worker_id,"CONTINUATION_WORKER_ID_INVALID")
    remaining=continuation.strings(remaining,"CONTINUATION_REMAINING_INVALID")
    if not remaining: raise RuntimeError("CONTINUATION_CREATE_REQUIRES_WORK")
    next_action=continuation.text(next_action,"CONTINUATION_NEXT_ACTION_INVALID")
    if branch is not None: branch=continuation.text(branch,"CONTINUATION_BRANCH_INVALID")
    if pr is not None and (type(pr) is not int or pr<=0): raise RuntimeError("CONTINUATION_PR_INVALID")
    if pr is not None and branch is None: raise RuntimeError("CONTINUATION_PR_REQUIRES_BRANCH")
    dependencies=continuation.strings(depends_on or [],"CONTINUATION_DEPENDENCIES_INVALID")
    if any(not continuation.ID_RE.fullmatch(dep) for dep in dependencies) or cid in dependencies: raise RuntimeError("CONTINUATION_DEPENDENCIES_INVALID")
    after={"schemaVersion":continuation.CURRENT_SCHEMA_VERSION,"id":cid,"workerId":worker_id,"status":WorkStatus.READY.value,"branch":branch,"prNumber":pr,"dependsOn":dependencies,"completed":[],"remaining":remaining,"nextAction":next_action,"lastKnownGood":{"sha":None,"checkpoint":None},"blockers":[],"handoffToWorkerId":None}
    return _build("create",None,after,{"workerId":worker_id,"remaining":remaining,"nextAction":next_action,"branch":branch,"prNumber":pr,"dependsOn":dependencies})


def advance(before: dict[str, Any], done: list[str], next_action: str | None = None, sha: str | None = None, checkpoint: str | None = None, *, inventory: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"] not in {WorkStatus.READY.value,WorkStatus.IN_PROGRESS.value}: raise RuntimeError("CONTINUATION_ADVANCE_STATUS_INVALID")
    work_graph.require_dependencies_done(continuation.operational_view(after),inventory)
    done=continuation.strings(done,"CONTINUATION_COMPLETE_INVALID")
    if not done: raise RuntimeError("CONTINUATION_ADVANCE_REQUIRES_COMPLETION")
    if any(item not in after["remaining"] for item in done): raise RuntimeError("CONTINUATION_COMPLETE_NOT_REMAINING")
    done_set=set(done); after["completed"].extend(done); after["remaining"]=[item for item in after["remaining"] if item not in done_set]; after["status"]=WorkStatus.IN_PROGRESS.value
    normalized_next=continuation.text(next_action,"CONTINUATION_NEXT_ACTION_REQUIRED") if after["remaining"] else None; after["nextAction"]=normalized_next
    if sha is not None:
        if not re.fullmatch(r"[0-9a-f]{40}",sha): raise RuntimeError("CONTINUATION_LAST_GOOD_SHA_INVALID")
        after["lastKnownGood"]["sha"]=sha
    normalized_checkpoint=None
    if checkpoint is not None: normalized_checkpoint=continuation.text(checkpoint,"CONTINUATION_LAST_GOOD_CHECKPOINT_INVALID"); after["lastKnownGood"]["checkpoint"]=normalized_checkpoint
    return _build("advance",before,after,{"completed":done,"nextAction":normalized_next,"lastGoodSha":sha,"checkpoint":normalized_checkpoint})


def wait(before: dict[str,Any], blockers: list[str]) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"] not in {WorkStatus.READY.value,WorkStatus.IN_PROGRESS.value}: raise RuntimeError("CONTINUATION_WAIT_STATUS_INVALID")
    blockers=continuation.strings(blockers,"CONTINUATION_BLOCKERS_INVALID")
    if not blockers: raise RuntimeError("CONTINUATION_WAIT_REQUIRES_BLOCKER")
    if after["nextAction"] is None: raise RuntimeError("CONTINUATION_WAIT_REQUIRES_NEXT_ACTION")
    after["status"]=WorkStatus.WAITING.value; after["blockers"]=blockers; after["handoffToWorkerId"]=None
    return _build("wait",before,after,{"blockers":blockers})


def handoff(before: dict[str,Any], target_worker: str, next_action: str) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"] not in {WorkStatus.READY.value,WorkStatus.IN_PROGRESS.value}: raise RuntimeError("CONTINUATION_HANDOFF_STATUS_INVALID")
    target_worker=continuation._worker(target_worker,"CONTINUATION_HANDOFF_WORKER_ID_INVALID"); next_action=continuation.text(next_action,"CONTINUATION_NEXT_ACTION_INVALID")
    after["status"]=WorkStatus.HANDOFF.value; after["nextAction"]=next_action; after["handoffToWorkerId"]=target_worker; after["blockers"]=[]
    return _build("handoff",before,after,{"toWorkerId":target_worker,"nextAction":next_action})


def resume(before: dict[str,Any], worker_id: str) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"] not in {WorkStatus.WAITING.value,WorkStatus.HANDOFF.value}: raise RuntimeError("CONTINUATION_RESUME_STATUS_INVALID")
    worker_id=continuation._worker(worker_id,"CONTINUATION_WORKER_ID_INVALID")
    if after["status"]==WorkStatus.HANDOFF.value and after["handoffToWorkerId"]!=worker_id: raise RuntimeError("CONTINUATION_HANDOFF_WORKER_MISMATCH")
    after["workerId"]=worker_id; after["blockers"]=[]; after["handoffToWorkerId"]=None; after["status"]=WorkStatus.IN_PROGRESS.value
    return _build("resume",before,after,{"workerId":worker_id})


def done(before: dict[str,Any], *, inventory: list[dict[str,Any]] | None = None) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"] not in {WorkStatus.READY.value,WorkStatus.IN_PROGRESS.value}: raise RuntimeError("CONTINUATION_DONE_STATUS_INVALID")
    work_graph.require_dependencies_done(continuation.operational_view(after),inventory)
    if after["remaining"]: raise RuntimeError("CONTINUATION_DONE_REMAINING_WORK")
    after["status"]=WorkStatus.DONE.value; after["nextAction"]=None; after["blockers"]=[]; after["handoffToWorkerId"]=None
    return _build("done",before,after,{})


def bind_execution(before: dict[str,Any], branch: str | None, pr: int | None = None) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"]==WorkStatus.DONE.value: raise RuntimeError("CONTINUATION_BIND_EXECUTION_STATUS_INVALID")
    if branch is not None: branch=continuation.text(branch,"CONTINUATION_BRANCH_INVALID")
    if pr is not None and (type(pr) is not int or pr<=0): raise RuntimeError("CONTINUATION_PR_INVALID")
    if pr is not None and branch is None: raise RuntimeError("CONTINUATION_PR_REQUIRES_BRANCH")
    after["branch"]=branch; after["prNumber"]=pr
    return _build("bind-execution",before,after,{"branch":branch,"prNumber":pr})


def restart(before: dict[str,Any], remaining: list[str], next_action: str) -> dict[str,Any]:
    after=copy.deepcopy(continuation.valid(before))
    if after["status"]!=WorkStatus.DONE.value: raise RuntimeError("CONTINUATION_RESTART_STATUS_INVALID")
    remaining=continuation.strings(remaining,"CONTINUATION_REMAINING_INVALID")
    if not remaining: raise RuntimeError("CONTINUATION_RESTART_REQUIRES_WORK")
    next_action=continuation.text(next_action,"CONTINUATION_NEXT_ACTION_INVALID")
    after["status"]=WorkStatus.READY.value; after["branch"]=None; after["prNumber"]=None; after["completed"]=[]; after["remaining"]=remaining; after["nextAction"]=next_action; after["lastKnownGood"]={"sha":None,"checkpoint":None}; after["blockers"]=[]; after["handoffToWorkerId"]=None
    return _build("restart",before,after,{"remaining":remaining,"nextAction":next_action})


def validate_work_inventory(items: dict[str,dict[str,Any]]) -> dict[str,Any]:
    if not isinstance(items,dict): raise RuntimeError("WORK_AUTHORITY_INVENTORY_INVALID")
    views=[]
    for cid in sorted(items): continuation.valid(items[cid],cid); views.append(continuation.operational_view(items[cid]))
    return work_graph.build(views)


def rebuild(plan: dict[str,Any], before: dict[str,Any] | None, *, inventory: list[dict[str,Any]] | None = None) -> dict[str,Any]:
    protocol.validate_plan(plan); action=plan["action"]; intent=plan["intent"]; cid=plan["subject"].get("id")
    if action=="create":
        if before is not None: raise RuntimeError("CONTINUATION_ALREADY_EXISTS")
        return create(cid,intent.get("workerId"),intent.get("remaining"),intent.get("nextAction"),intent.get("branch"),intent.get("prNumber"),depends_on=intent.get("dependsOn"))
    if before is None: raise RuntimeError("CONTINUATION_FILE_MISSING")
    continuation.valid(before,cid)
    if action=="advance": return advance(before,intent.get("completed"),intent.get("nextAction"),intent.get("lastGoodSha"),intent.get("checkpoint"),inventory=inventory)
    if action=="wait": return wait(before,intent.get("blockers"))
    if action=="handoff": return handoff(before,intent.get("toWorkerId"),intent.get("nextAction"))
    if action=="resume": return resume(before,intent.get("workerId"))
    if action=="done": return done(before,inventory=inventory)
    if action=="bind-execution": return bind_execution(before,intent.get("branch"),intent.get("prNumber"))
    if action=="restart": return restart(before,intent.get("remaining"),intent.get("nextAction"))
    raise RuntimeError("CONTINUATION_COMMAND_INVALID")


def validate_plan(plan: dict[str,Any], before: dict[str,Any] | None = None, *, repository: str = DEFAULT_REPOSITORY, authority_branch: str = DEFAULT_BRANCH, state_dir: str = DEFAULT_DIR, bind_before: bool = False, inventory: list[dict[str,Any]] | None = None) -> dict[str,Any]:
    protocol.validate_plan(plan)
    if plan["domain"]!="continuation": raise RuntimeError("CONTINUATION_PLAN_DOMAIN_INVALID")
    subject=plan["subject"]
    if subject.get("kind")!="continuation" or not continuation.ID_RE.fullmatch(str(subject.get("id") or "")): raise RuntimeError("CONTINUATION_PLAN_SUBJECT_INVALID")
    if plan["authority"]!=_authority(repository,authority_branch,state_dir): raise RuntimeError("CONTINUATION_PLAN_AUTHORITY_INVALID")
    continuation.valid(plan["candidate"],subject["id"])
    if bind_before:
        if continuation.state_hash(before)!=plan["beforeStateHash"]: raise RuntimeError("CONTINUATION_PLAN_STALE")
        if rebuild(plan,before,inventory=inventory)!=plan: raise RuntimeError("CONTINUATION_PLAN_STALE")
    return plan
