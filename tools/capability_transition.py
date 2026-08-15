"""Pure deterministic transition planning for capability Gates."""
from __future__ import annotations
import copy, re
from typing import Any
from tools import capability_gates as gates

PLAN_SCHEMA = "CapabilityTransitionPlan 0.1"


def state_hash(value: dict[str, Any] | None) -> str | None:
    return None if value is None else gates.stable_hash(value)


def text(value, code):
    if not isinstance(value, str) or not value.strip(): raise RuntimeError(code)
    return value.strip()


def ident(value, code):
    if not isinstance(value, str) or not gates.ID_RE.fullmatch(value): raise RuntimeError(code)
    return value


def refs(values):
    out=[]
    for value in values or []:
        value=text(value,"CAPABILITY_EVIDENCE_INVALID")
        if value not in out: out.append(value)
    return out


def valid(value, expected_id=None):
    errors=gates.validate_capability(value, expected_id=expected_id)
    if errors: raise RuntimeError(errors[0])
    return value


def experimental(value):
    value=copy.deepcopy(valid(value))
    if value["policy"]!="experimental": raise RuntimeError("CAPABILITY_NOT_EXPERIMENTAL")
    return value


def build(capability_id, action, before, after, *, details=None, evidence=None):
    ident(capability_id,"CAPABILITY_ID_INVALID")
    if before is not None: valid(before, capability_id)
    valid(after, capability_id)
    details=copy.deepcopy(details or {}); evidence=refs(evidence)
    core={"schemaVersion":PLAN_SCHEMA,"capability":capability_id,"action":action,"beforeStateHash":state_hash(before),"afterStateHash":state_hash(after),"details":details,"evidence":evidence}
    plan_hash=gates.stable_hash(core)
    subject=details.get("gateId") or (details.get("gate") or {}).get("id") or action
    subject=re.sub(r"[^a-z0-9-]+","-",str(subject).lower()).strip("-") or action
    return {**core,"planHash":plan_hash,"evidencePath":f"ops/evidence/capability-gates/{capability_id}/{action}-{subject}-{plan_hash[:16]}.json","after":after}


def init(capability_id, gate_defs, *, max_empty_rounds=3, defer_reason=None):
    ident(capability_id,"CAPABILITY_ID_INVALID")
    if type(max_empty_rounds) is not int or max_empty_rounds<1: raise RuntimeError("CAPABILITY_MAX_EMPTY_ROUNDS_INVALID")
    backlog=[]; seen=set()
    for raw in gate_defs:
        gid=ident(raw.get("id"),"CAPABILITY_GATE_ID_INVALID"); test=text(raw.get("test"),"CAPABILITY_GATE_TEST_INVALID")
        if gid in seen: raise RuntimeError("CAPABILITY_GATE_ID_DUPLICATE")
        seen.add(gid); backlog.append({"id":gid,"test":test})
    backlog.sort(key=lambda g:g["id"])
    if not backlog and defer_reason is None: raise RuntimeError("CAPABILITY_INIT_REQUIRES_GATE_OR_DEFER_REASON")
    reason=None if defer_reason is None else text(defer_reason,"CAPABILITY_DEFER_REASON_INVALID")
    after={"schemaVersion":gates.SUPPORTED_SCHEMA,"id":capability_id,"policy":"experimental","gates":{"backlog":backlog,"next":[g["id"] for g in backlog]},"roundsWithoutActiveGates":0,"maxRoundsWithoutActiveGates":max_empty_rounds,"deferReason":None if backlog else reason}
    return build(capability_id,"init",None,after,details={"gates":backlog,"maxRoundsWithoutActiveGates":max_empty_rounds,"deferReason":after["deferReason"]})


def gate_add(before, gate_id, test):
    after=experimental(before); gate_id=ident(gate_id,"CAPABILITY_GATE_ID_INVALID"); test=text(test,"CAPABILITY_GATE_TEST_INVALID")
    if any(g["id"]==gate_id for g in after["gates"]["backlog"]): raise RuntimeError("CAPABILITY_GATE_ID_DUPLICATE")
    after["gates"]["backlog"].append({"id":gate_id,"test":test}); after["gates"]["backlog"].sort(key=lambda g:g["id"])
    after["gates"]["next"]=sorted(set([*after["gates"]["next"],gate_id])); after["roundsWithoutActiveGates"]=0; after["deferReason"]=None
    return build(after["id"],"gate-add",before,after,details={"gate":{"id":gate_id,"test":test}})


def select_next(before, gate_ids):
    after=experimental(before)
    if not gate_ids: raise RuntimeError("CAPABILITY_NEXT_REQUIRES_GATE")
    chosen=sorted(set(ident(g,"CAPABILITY_GATE_ID_INVALID") for g in gate_ids)); backlog={g["id"] for g in after["gates"]["backlog"]}
    if any(g not in backlog for g in chosen): raise RuntimeError("CAPABILITY_NEXT_GATE_NOT_IN_BACKLOG")
    after["gates"]["next"]=chosen; after["roundsWithoutActiveGates"]=0; after["deferReason"]=None
    return build(after["id"],"next",before,after,details={"gateIds":chosen})


def set_supervisor_participation(before, mode):
    after=copy.deepcopy(valid(before)); mode=text(mode,"CAPABILITY_SUPERVISOR_PARTICIPATION_INVALID")
    if mode not in gates.SUPERVISOR_PARTICIPATION: raise RuntimeError("CAPABILITY_SUPERVISOR_PARTICIPATION_INVALID")
    if gates.supervisor_participation(after)==mode: raise RuntimeError("CAPABILITY_SUPERVISOR_PARTICIPATION_UNCHANGED")
    after["supervisorParticipation"]=mode
    return build(after["id"],"supervisor-participation",before,after,details={"mode":mode})


def passed(before, gate_id, evidence):
    after=experimental(before); gate_id=ident(gate_id,"CAPABILITY_GATE_ID_INVALID"); evidence=refs(evidence)
    if not evidence: raise RuntimeError("CAPABILITY_PASS_REQUIRES_EVIDENCE")
    if gate_id not in after["gates"]["next"]: raise RuntimeError("CAPABILITY_GATE_NOT_ACTIVE")
    after["gates"]["backlog"]=[g for g in after["gates"]["backlog"] if g["id"]!=gate_id]; after["gates"]["next"]=[g for g in after["gates"]["next"] if g!=gate_id]
    after["roundsWithoutActiveGates"]=0; after["deferReason"]=None
    return build(after["id"],"pass",before,after,details={"gateId":gate_id},evidence=evidence)


def failed(before, gate_id, evidence):
    after=experimental(before); gate_id=ident(gate_id,"CAPABILITY_GATE_ID_INVALID"); evidence=refs(evidence)
    if not evidence: raise RuntimeError("CAPABILITY_FAIL_REQUIRES_EVIDENCE")
    if gate_id not in after["gates"]["next"]: raise RuntimeError("CAPABILITY_GATE_NOT_ACTIVE")
    return build(after["id"],"fail",before,after,details={"gateId":gate_id},evidence=evidence)


def defer(before, reason):
    after=experimental(before); reason=text(reason,"CAPABILITY_DEFER_REASON_INVALID")
    if after["gates"]["next"]: raise RuntimeError("CAPABILITY_DEFER_REQUIRES_EMPTY_NEXT")
    if after["roundsWithoutActiveGates"]>=after["maxRoundsWithoutActiveGates"]: raise RuntimeError("CAPABILITY_EMPTY_ROUND_LIMIT_REACHED")
    after["roundsWithoutActiveGates"]+=1; after["deferReason"]=reason
    return build(after["id"],"defer",before,after,details={"reason":reason})


def review_limit(before, new_max, reason):
    after=experimental(before); reason=text(reason,"CAPABILITY_DEFER_REASON_INVALID")
    if after["gates"]["next"]: raise RuntimeError("CAPABILITY_REVIEW_LIMIT_REQUIRES_EMPTY_NEXT")
    if after["roundsWithoutActiveGates"]<after["maxRoundsWithoutActiveGates"]: raise RuntimeError("CAPABILITY_REVIEW_LIMIT_NOT_DUE")
    if type(new_max) is not int or new_max<=after["roundsWithoutActiveGates"]: raise RuntimeError("CAPABILITY_REVIEW_LIMIT_INVALID")
    if new_max==after["maxRoundsWithoutActiveGates"]: raise RuntimeError("CAPABILITY_REVIEW_LIMIT_UNCHANGED")
    after["maxRoundsWithoutActiveGates"]=new_max; after["deferReason"]=reason
    return build(after["id"],"review-limit",before,after,details={"maxRoundsWithoutActiveGates":new_max,"reason":reason})


def promote(before, evidence):
    after=experimental(before); evidence=refs(evidence)
    if not evidence: raise RuntimeError("CAPABILITY_PROMOTE_REQUIRES_EVIDENCE")
    if after["gates"]["backlog"] or after["gates"]["next"]: raise RuntimeError("CAPABILITY_PROMOTE_REQUIRES_EMPTY_BACKLOG")
    if after["deferReason"] is not None: raise RuntimeError("CAPABILITY_PROMOTE_REQUIRES_NO_DEFER_REASON")
    after["policy"]="canonical"; after["roundsWithoutActiveGates"]=0
    return build(after["id"],"promote",before,after,evidence=evidence)


def disable(before, reason):
    after=copy.deepcopy(valid(before)); reason=text(reason,"CAPABILITY_DISABLE_REASON_INVALID")
    if after["policy"]=="disabled": raise RuntimeError("CAPABILITY_ALREADY_DISABLED")
    after["policy"]="disabled"; after["gates"]["next"]=[]; after["roundsWithoutActiveGates"]=0; after["deferReason"]=None
    return build(after["id"],"disable",before,after,details={"reason":reason})
