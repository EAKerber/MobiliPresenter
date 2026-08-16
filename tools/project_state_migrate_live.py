#!/usr/bin/env python3
"""Temporary M4B runner for the one-time ProjectState 1.0 -> 2.0 authority migration."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_state, project_state_apply, project_state_transition, publication
from tools import transition_protocol as protocol

WORK_BRANCH = "work/operations/project-state-v2-migration"
EVIDENCE_PATH = ROOT / "ops" / "evidence" / "project-state" / "project-state-2.0-migration.json"


def run_git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_GIT_FAILED:{' '.join(args)}:{(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip()


def observed_git() -> dict[str, Any]:
    branch = run_git("branch", "--show-current") or os.environ.get("GITHUB_REF_NAME") or ""
    dirty = bool(run_git("status", "--porcelain"))
    return {"worktree": True, "branch": branch, "dirty": dirty}


def observe_control_head() -> str:
    return run_git("rev-parse", "origin/main")


def observe_state_blob() -> str:
    return run_git("hash-object", "ops/state/project.json")


def load_mapping() -> dict[str, Any]:
    return project_state.load_json(project_state.MIGRATION_MAP_PATH)


def build_plan() -> dict[str, Any]:
    before = project_state.load_state()
    mapping = load_mapping()
    return project_state_transition.schema_migration(
        before,
        mapping,
        source_control_head=observe_control_head(),
        source_state_blob_sha=observe_state_blob(),
        work_branch=WORK_BRANCH,
        source_validator=project_state.validate_v1,
        target_validator=project_state.validate_v2,
        migrate=project_state.migrate_v1_to_v2,
        validate_migration_map=project_state.validate_migration_map,
    )


def publication_parity(before: dict[str, Any]) -> dict[str, Any]:
    manifest = publication.load_manifest(before["published"]["artifactManifest"])
    return {
        "release": before["published"]["release"] == manifest["release"],
        "sourceBranch": before["git"]["publishedBranch"] == manifest["sourceBranch"],
        "sourceBuildFingerprint": before["published"]["artifactSha256"] == manifest["sha256"],
        "all": (
            before["published"]["release"] == manifest["release"]
            and before["git"]["publishedBranch"] == manifest["sourceBranch"]
            and before["published"]["artifactSha256"] == manifest["sha256"]
        ),
    }


def build_evidence(before: dict[str, Any], mapping: dict[str, Any], plan: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    constraint_mappings = mapping.get("constraintMappings") if isinstance(mapping.get("constraintMappings"), list) else []
    unresolved = [item for item in constraint_mappings if not isinstance(item, dict) or item.get("status") != "resolved"]
    parity = publication_parity(before)
    protected_parity = plan["candidate"]["git"]["protectedBranches"] == before["git"]["preserveBranches"]
    if not parity["all"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PUBLICATION_PARITY_FAILED")
    if not protected_parity:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PROTECTED_BRANCH_PARITY_FAILED")
    return {
        "schemaVersion": "ProjectStateMigrationEvidence 0.1",
        "sourceControlHead": plan["intent"]["sourceControlHead"],
        "sourceStateBlobSha": plan["intent"]["sourceStateBlobSha"],
        "fromSchemaVersion": plan["intent"]["fromSchemaVersion"],
        "toSchemaVersion": plan["intent"]["toSchemaVersion"],
        "migrationMap": {
            "historicalRevision": plan["intent"]["sourceControlHead"],
            "path": plan["intent"]["migrationMapPath"],
            "hash": plan["intent"]["migrationMapHash"],
            "constraintCount": len(constraint_mappings),
            "unresolvedCount": len(unresolved),
        },
        "publicationParity": parity,
        "protectedBranchesParity": protected_parity,
        "transitionPlan": plan,
        "transitionReceipt": receipt,
    }


def write_evidence(value: dict[str, Any]) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_plan(plan: dict[str, Any], expected_plan: str | None, authorized: bool) -> dict[str, Any]:
    before = project_state.load_state()
    mapping = load_mapping()
    parity = publication_parity(before)
    if not parity["all"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PUBLICATION_PARITY_FAILED")
    if project_state.validate_migration_map(mapping, before):
        raise RuntimeError("PROJECT_STATE_MIGRATION_MAP_INVALID")
    receipt = project_state_apply.apply_schema_migration(
        plan,
        expected_plan,
        authorized=authorized,
        state_path=project_state.STATE_PATH,
        load_state=project_state.load_state,
        source_validator=project_state.validate_v1,
        target_validator=project_state.validate_v2,
        migration_map_loader=load_mapping,
        validate_migration_map=project_state.validate_migration_map,
        migrate=project_state.migrate_v1_to_v2,
        observe_git=observed_git,
        observe_control_head=observe_control_head,
        observe_state_blob=observe_state_blob,
    )
    evidence = build_evidence(before, mapping, plan, receipt)
    write_evidence(evidence)
    return {"receipt": receipt, "evidencePath": str(EVIDENCE_PATH.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser(prog="project-state-migrate-live")
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--plan")
    parser.add_argument("--expected-plan")
    parser.add_argument("--authorize-schema-migration", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            payload = build_plan()
        else:
            if not args.plan:
                raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_FILE_REQUIRED")
            plan_path = Path(args.plan)
            payload = apply_plan(
                json.loads(plan_path.read_text(encoding="utf-8")),
                args.expected_plan,
                args.authorize_schema_migration,
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else payload.get("planHash", "APPLIED"))
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
