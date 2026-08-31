from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from tools import project_state
from tools import project_state_apply
from tools import project_state_transition
from tools import roadmap_freshness

EXPECTED_BEFORE_CHECKPOINT = "M12-AT3D-R5A1-HOSTED-RUNTIME-OBSERVATION-INGRESS-QUALIFIED"
EXPECTED_BEFORE_NEXT = "resolve-m12-at3d-r5a2-work-mode-host-observation-surface-v0.1"
CHECKPOINT = "M12-MATURITY-PROOF-0.1-PASSED"
NEXT_TRANSITION = "implement-m13-reflection-and-operational-quiescence-v0.1"
CLOSURE_PATH = project_state.ROOT / "docs/experiments/m12-final-maturity-proof-closure-v0.1.md"
OUT = Path("/tmp/m12-final-maturity-project-state-reconcile")


def observe_git() -> dict[str, object]:
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_state.ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project_state.ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_state.ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "worktree": inside.returncode == 0 and inside.stdout.strip() == "true",
        "branch": branch.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
    }


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = project_state.load_state()
    development = before["development"]
    if development["checkpoint"] != EXPECTED_BEFORE_CHECKPOINT:
        raise SystemExit("M12_FINAL_MATURITY_BEFORE_CHECKPOINT_DRIFT")
    if development["nextTransition"] != EXPECTED_BEFORE_NEXT:
        raise SystemExit("M12_FINAL_MATURITY_BEFORE_NEXT_TRANSITION_DRIFT")
    if not CLOSURE_PATH.is_file():
        raise SystemExit("M12_FINAL_MATURITY_CLOSURE_MISSING")

    plan = project_state_transition.checkpoint(
        before,
        CHECKPOINT,
        NEXT_TRANSITION,
        None,
        validator=project_state.validate_current,
    )
    project_state_transition.validate_project_state_plan(
        plan,
        validator=project_state.validate_current,
        before=before,
        bind_before=True,
    )
    write_json(OUT / "transition-plan.json", plan)

    receipt = project_state_apply.apply(
        plan,
        plan["planHash"],
        state_path=project_state.STATE_PATH,
        load_state=project_state.load_state,
        validator=project_state.validate_current,
        observe_git=observe_git,
    )
    write_json(OUT / "transition-receipt.json", receipt)

    after = project_state.load_state()
    required = roadmap_freshness.discover_consumers(after)
    consumers = []
    before_contents: dict[str, bytes] = {}
    after_contents: dict[str, bytes] = {}
    for relative in required:
        content = (project_state.ROOT / relative).read_bytes()
        before_contents[relative] = content
        after_contents[relative] = content
        consumers.append(
            {
                "path": relative,
                "disposition": "NO_CHANGE",
                "contentHash": hashlib.sha256(content).hexdigest(),
            }
        )

    coverage = {
        "schemaVersion": roadmap_freshness.SCHEMA_VERSION,
        "projectState": {
            "baseHash": plan["beforeStateHash"],
            "currentHash": plan["afterStateHash"],
            "changedFields": [
                "development.checkpoint",
                "development.nextTransition",
            ],
        },
        "consumers": consumers,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    write_json(roadmap_freshness.COVERAGE_PATH, coverage)

    errors = roadmap_freshness.validate_coverage(coverage)
    if errors:
        raise SystemExit("ROADMAP_FRESHNESS_VALIDATE_FAILED:" + errors[0])
    inspection = roadmap_freshness.inspect_transition(
        before,
        after,
        before_contents,
        after_contents,
        coverage,
        required,
    )
    write_json(OUT / "roadmap-freshness-inspection.json", inspection)
    if inspection["status"] != "PASS":
        raise SystemExit("ROADMAP_FRESHNESS_INSPECTION_FAILED:" + inspection["code"])

    summary = {
        "schemaVersion": "M12FinalMaturityProjectStateReconcileQualification 0.1",
        "checkpoint": CHECKPOINT,
        "nextTransition": NEXT_TRANSITION,
        "beforeStateHash": plan["beforeStateHash"],
        "afterStateHash": plan["afterStateHash"],
        "planHash": plan["planHash"],
        "receiptHash": receipt["receiptHash"],
        "receiptVerified": receipt["verified"],
        "roadmapFreshnessStatus": inspection["status"],
        "changedFields": coverage["projectState"]["changedFields"],
        "status": "PASS",
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
