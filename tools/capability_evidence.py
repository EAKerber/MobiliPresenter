"""Transition evidence records and deterministic replay."""
from __future__ import annotations
import copy
from typing import Any
from tools import capability_transition as tx

SCHEMA="CapabilityGateTransitionEvidence 0.1"


def record(plan):
    return {"schemaVersion":SCHEMA,**{k:copy.deepcopy(plan[k]) for k in ("capability","action","planHash","beforeStateHash","afterStateHash","details","evidence","evidencePath")}}


def validate(value):
    expected={"schemaVersion","capability","action","planHash","beforeStateHash","afterStateHash","details","evidence","evidencePath"}; errors=[]
    if set(value)!=expected: errors.append("CAPABILITY_EVIDENCE_FIELDS_INVALID")
    if value.get("schemaVersion")!=SCHEMA: errors.append("CAPABILITY_EVIDENCE_SCHEMA_UNSUPPORTED")
    try: tx.ident(value.get("capability"),"CAPABILITY_EVIDENCE_ID_INVALID")
    except RuntimeError as exc: errors.append(str(exc))
    if not isinstance(value.get("details"),dict): errors.append("CAPABILITY_EVIDENCE_DETAILS_INVALID")
    if not isinstance(value.get("evidence"),list): errors.append("CAPABILITY_EVIDENCE_REFS_INVALID")
    for key in ("action","planHash","afterStateHash","evidencePath"):
        if not isinstance(value.get(key),str) or not value[key]: errors.append(f"CAPABILITY_EVIDENCE_{key.upper()}_INVALID")
    if value.get("beforeStateHash") is not None and not isinstance(value.get("beforeStateHash"),str): errors.append("CAPABILITY_EVIDENCE_BEFORESTATEHASH_INVALID")
    return errors


def rebuild(before:dict[str,Any]|None, value):
    action=value.get("action"); details=value.get("details") or {}; refs=value.get("evidence") or []
    if action=="init": return tx.init(value.get("capability"),details.get("gates",[]),max_empty_rounds=details.get("maxRoundsWithoutActiveGates"),defer_reason=details.get("deferReason"))
    if before is None: raise RuntimeError("CAPABILITY_EVIDENCE_BEFORE_MISSING")
    if action=="gate-add":
        gate=details.get("gate") or {}; return tx.gate_add(before,gate.get("id"),gate.get("test"))
    if action=="next": return tx.select_next(before,details.get("gateIds",[]))
    if action=="pass": return tx.passed(before,details.get("gateId"),refs)
    if action=="fail": return tx.failed(before,details.get("gateId"),refs)
    if action=="defer": return tx.defer(before,details.get("reason"))
    if action=="review-limit": return tx.review_limit(before,details.get("maxRoundsWithoutActiveGates"),details.get("reason"))
    if action=="promote": return tx.promote(before,refs)
    if action=="disable": return tx.disable(before,details.get("reason"))
    raise RuntimeError("CAPABILITY_EVIDENCE_ACTION_INVALID")
