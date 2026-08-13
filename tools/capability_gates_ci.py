#!/usr/bin/env python3
"""CI guard: capability state changes must be explained by immutable transition evidence."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools import capability_gates as gates
from tools import capability_transition as tx
from tools import capability_evidence as ev
ERROR_EXIT=2; CAP_PREFIX="ops/capabilities/"; EVIDENCE_PREFIX="ops/evidence/capability-gates/"


def run_git(args):
    proc=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,check=False)
    if proc.returncode!=0: raise RuntimeError(f"CAPABILITY_CI_GIT_ERROR:{(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def changed_paths(base,head):
    out=run_git(["diff","--name-status",f"{base}...{head}","--","ops/capabilities","ops/evidence/capability-gates"]); result=[]
    for line in out.splitlines():
        if line.strip():
            parts=line.split("\t"); result.append((parts[0],parts[-1]))
    return result


def git_json(ref,path):
    proc=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,text=True,capture_output=True,check=False)
    if proc.returncode!=0: return None
    try: value=json.loads(proc.stdout)
    except json.JSONDecodeError as exc: raise RuntimeError(f"CAPABILITY_CI_JSON_INVALID:{path}") from exc
    if not isinstance(value,dict): raise RuntimeError(f"CAPABILITY_CI_JSON_ROOT_INVALID:{path}")
    return value


def capability_id(path):
    if path.startswith(CAP_PREFIX) and path.endswith(".json"): return Path(path).stem
    if path.startswith(EVIDENCE_PREFIX) and path.endswith(".json"):
        rel=path[len(EVIDENCE_PREFIX):]; parts=rel.split("/",1); return parts[0] if len(parts)==2 else None
    return None


def replay(before,after,records):
    current=before; pending=list(records)
    while pending:
        current_hash=tx.state_hash(current); candidates=[r for r in pending if r.get("beforeStateHash")==current_hash]
        if not candidates: raise RuntimeError("CAPABILITY_EVIDENCE_CHAIN_BROKEN")
        noop=sorted([r for r in candidates if r.get("afterStateHash")==current_hash],key=lambda r:r["planHash"])
        advancing=[r for r in candidates if r.get("afterStateHash")!=current_hash]
        for record in noop:
            rebuilt=ev.rebuild(current,record)
            if rebuilt["planHash"]!=record["planHash"]: raise RuntimeError("CAPABILITY_EVIDENCE_PLAN_MISMATCH")
            pending.remove(record)
        if len(advancing)>1: raise RuntimeError("CAPABILITY_EVIDENCE_CHAIN_AMBIGUOUS")
        if advancing:
            record=advancing[0]; rebuilt=ev.rebuild(current,record)
            if rebuilt["planHash"]!=record["planHash"]: raise RuntimeError("CAPABILITY_EVIDENCE_PLAN_MISMATCH")
            if rebuilt["beforeStateHash"]!=record["beforeStateHash"] or rebuilt["afterStateHash"]!=record["afterStateHash"]: raise RuntimeError("CAPABILITY_EVIDENCE_STATE_HASH_MISMATCH")
            current=rebuilt["after"]; pending.remove(record)
        elif not noop: raise RuntimeError("CAPABILITY_EVIDENCE_CHAIN_STALLED")
    if tx.state_hash(current)!=tx.state_hash(after): raise RuntimeError("CAPABILITY_HEAD_STATE_NOT_EXPLAINED")
    return current


def validate_changes(base,head):
    ids=set(); evidence_paths={}
    for status,path in changed_paths(base,head):
        cid=capability_id(path)
        if cid: ids.add(cid)
        if path.startswith(EVIDENCE_PREFIX):
            if not status.startswith("A"): raise RuntimeError("CAPABILITY_EVIDENCE_IMMUTABLE")
            if cid: evidence_paths.setdefault(cid,[]).append(path)
        elif path.startswith(CAP_PREFIX) and path.endswith(".json") and (status.startswith("D") or status.startswith("R")):
            raise RuntimeError("CAPABILITY_STATE_DELETE_FORBIDDEN")
    validated=[]
    for cid in sorted(ids):
        path=f"{CAP_PREFIX}{cid}.json"; before=git_json(base,path); after=git_json(head,path)
        if before is not None:
            errors=gates.validate_capability(before,expected_id=cid)
            if errors: raise RuntimeError(f"{errors[0]}:{cid}:base")
        if after is not None:
            errors=gates.validate_capability(after,expected_id=cid)
            if errors: raise RuntimeError(f"{errors[0]}:{cid}:head")
        records=[]
        for evidence_path in sorted(evidence_paths.get(cid,[])):
            record=git_json(head,evidence_path)
            if record is None: raise RuntimeError("CAPABILITY_EVIDENCE_MISSING_AT_HEAD")
            errors=ev.validate(record)
            if errors: raise RuntimeError(errors[0])
            if record["evidencePath"]!=evidence_path: raise RuntimeError("CAPABILITY_EVIDENCE_PATH_MISMATCH")
            if record["capability"]!=cid: raise RuntimeError("CAPABILITY_EVIDENCE_ID_PATH_MISMATCH")
            records.append(record)
        if tx.state_hash(before)!=tx.state_hash(after) and not records: raise RuntimeError("CAPABILITY_STATE_CHANGE_WITHOUT_EVIDENCE")
        if records: replay(before,after,records)
        validated.append({"id":cid,"stateChanged":tx.state_hash(before)!=tx.state_hash(after),"evidenceCount":len(records)})
    return {"ok":True,"schemaVersion":"CapabilityLifecycleGuard 0.1","baseSha":base,"headSha":head,"validated":validated}


def main(argv=None):
    p=argparse.ArgumentParser(prog="capability-gates-ci"); p.add_argument("--base-sha",required=True); p.add_argument("--head-sha",default="HEAD"); p.add_argument("--json",action="store_true",dest="as_json"); args=p.parse_args(argv)
    try: payload=validate_changes(args.base_sha,args.head_sha); code=0
    except RuntimeError as exc: payload={"ok":False,"error":str(exc)}; code=ERROR_EXIT
    print(json.dumps(payload,indent=2 if args.as_json else None,ensure_ascii=False)); return code


if __name__=="__main__": raise SystemExit(main())
