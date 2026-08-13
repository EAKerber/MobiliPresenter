"""Fail-closed local apply + readback for capability transition plans."""
from __future__ import annotations
import json, os
from pathlib import Path
from tools import capability_gates as gates
from tools import capability_transition as tx
from tools import capability_evidence as ev

ROOT=Path(__file__).resolve().parents[1]
CAPABILITY_DIR=ROOT/"ops"/"capabilities"


def apply(plan, expected_plan):
    if expected_plan!=plan["planHash"]: raise RuntimeError("CAPABILITY_PLAN_HASH_MISMATCH")
    state_path=CAPABILITY_DIR/f"{plan['capability']}.json"; evidence_path=ROOT/plan["evidencePath"]
    if evidence_path.exists(): raise RuntimeError("CAPABILITY_EVIDENCE_ALREADY_EXISTS")
    if plan["beforeStateHash"] is None:
        if state_path.exists(): raise RuntimeError("CAPABILITY_INIT_ALREADY_EXISTS")
    elif tx.state_hash(gates.load_capability(plan["capability"]))!=plan["beforeStateHash"]: raise RuntimeError("CAPABILITY_PLAN_STALE")
    state_path.parent.mkdir(parents=True,exist_ok=True); evidence_path.parent.mkdir(parents=True,exist_ok=True)
    previous=state_path.read_text(encoding="utf-8") if state_path.exists() else None; changed=plan["beforeStateHash"]!=plan["afterStateHash"]
    state_tmp=state_path.with_suffix(".json.tmp"); evidence_tmp=evidence_path.with_suffix(".json.tmp")
    try:
        if changed: state_tmp.write_text(json.dumps(plan["after"],indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        evidence_tmp.write_text(json.dumps(ev.record(plan),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        if changed: os.replace(state_tmp,state_path)
        os.replace(evidence_tmp,evidence_path)
    except Exception:
        for path in (state_tmp,evidence_tmp):
            if path.exists(): path.unlink()
        if changed:
            if previous is None and state_path.exists(): state_path.unlink()
            elif previous is not None: state_path.write_text(previous,encoding="utf-8")
        if evidence_path.exists(): evidence_path.unlink()
        raise
    if tx.state_hash(gates.load_capability(plan["capability"]))!=plan["afterStateHash"]: raise RuntimeError("CAPABILITY_APPLY_READBACK_STATE_MISMATCH")
    if gates.load_json(evidence_path)!=ev.record(plan): raise RuntimeError("CAPABILITY_APPLY_READBACK_EVIDENCE_MISMATCH")
    return {"ok":True,"applied":True,"capability":plan["capability"],"action":plan["action"],"planHash":plan["planHash"],"evidencePath":plan["evidencePath"],"afterStateHash":plan["afterStateHash"]}
