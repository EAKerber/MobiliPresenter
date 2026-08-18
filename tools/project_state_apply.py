"""Fail-closed ProjectState executor for Transition Protocol 0.1 plans."""
from __future__ import annotations

import json,os,tempfile
from pathlib import Path
from typing import Any,Callable

from tools import project_state_transition as transition
from tools import transition_protocol as protocol
from tools.semantics.branches import parse_branch_name

Loader=Callable[[],dict[str,Any]];Validator=Callable[[dict[str,Any]],list[dict[str,str]]];GitObserver=Callable[[],dict[str,Any]]

def _atomic_write(path,payload):
    encoded=json.dumps(payload,indent=2,ensure_ascii=False)+"\n"
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as handle:handle.write(encoded);temporary=Path(handle.name)
    try:os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
def _restore_bytes(path,previous_bytes):
    with tempfile.NamedTemporaryFile("wb",dir=path.parent,delete=False) as handle:handle.write(previous_bytes);restore_tmp=Path(handle.name)
    try:os.replace(restore_tmp,path)
    finally:
        if restore_tmp.exists():restore_tmp.unlink()
def checkpoint_branch_allowed(branch):
    if not isinstance(branch,str) or not branch:return False
    try:identity=parse_branch_name(branch)
    except RuntimeError:return False
    return identity.get("grammar")=="canonical" and identity.get("declaredClass")=="work" and identity.get("semanticDomain")=="operations"
def apply(plan,expected_plan,*,state_path,load_state,validator,observe_git):
    transition.validate_project_state_plan(plan,validator=validator);protocol.require_expected_plan(plan,expected_plan);current=load_state();errors=validator(current)
    if errors:raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    transition.validate_project_state_plan(plan,validator=validator,before=current,bind_before=True);git=observe_git()
    if not git.get("worktree"):raise RuntimeError("CHECKPOINT_NOT_A_WORKTREE")
    branch=git.get("branch")
    if not checkpoint_branch_allowed(branch):raise RuntimeError(f"CHECKPOINT_BRANCH_NOT_AUTHORIZED:{branch}")
    if git.get("dirty"):raise RuntimeError("CHECKPOINT_DIRTY_WORKTREE")
    previous_bytes=state_path.read_bytes();wrote=False
    try:
        _atomic_write(state_path,plan["candidate"]);wrote=True;readback=load_state();errors=validator(readback)
        if errors:raise RuntimeError(f"STATE_READBACK_INVALID:{errors[0]['detail']}")
        receipt=protocol.build_receipt(plan,readback);protocol.validate_receipt(receipt,plan);return receipt
    except Exception:
        if wrote:
            _restore_bytes(state_path,previous_bytes);restored=load_state()
            if protocol.state_hash(restored)!=plan["beforeStateHash"]:raise RuntimeError("PROJECT_STATE_ROLLBACK_FAILED")
        raise
