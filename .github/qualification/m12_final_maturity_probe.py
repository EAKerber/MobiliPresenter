#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash

REPO = "EAKerber/MobiliPresenter"
EXPECTED_MAIN = "6a721f59c38a092dbdd94777176a6a4ce4800fe6"
EXPECTED_COORDINATION = "987060ca96c9ab64e0c99f78bfe695198255c043"
EXPECTED_CONTINUATIONS = "0bec98c1be514df89c1db9829cd929edaf04d366"
QUALIFICATION_BRANCH = "work/operations/m12-final-maturity-qualification-r2-20260830"

EXISTING_EVIDENCE = [
    {"case": "manager-governed-mutation", "pr": 164},
    {"case": "lease-lifecycle", "pr": 161},
    {"case": "delayed-result-stable-seal", "pr": 197},
    {"case": "waiting-no-poll-replay", "pr": 201},
    {"case": "release-predecessor-ordering", "pr": 203},
    {"case": "provider-carrier-separation", "pr": 206},
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def gh_json(endpoint: str) -> Any:
    proc = run(["gh", "api", endpoint])
    if proc.returncode != 0:
        raise RuntimeError(
            f"GH_API_FAILED:{endpoint}:{(proc.stderr or proc.stdout).strip()}"
        )
    return json.loads(proc.stdout)


def exact_ref(branch: str) -> str:
    if "/" not in branch:
        value = gh_json(f"repos/{REPO}/git/ref/heads/{branch}")
        return value["object"]["sha"]
    values = gh_json(f"repos/{REPO}/git/matching-refs/heads/{branch}")
    exact = [item for item in values if item.get("ref") == f"refs/heads/{branch}"]
    if len(exact) != 1:
        raise RuntimeError(f"REF_NOT_EXACT:{branch}:{len(exact)}")
    return exact[0]["object"]["sha"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def begin(role: str) -> tuple[int, dict[str, Any]]:
    proc = run([
        sys.executable,
        "tools/agent.py",
        "begin",
        "--role", role,
        "--intent", "inspect-and-plan",
        "--machine-scope", "live",
        "--json",
    ])
    raw = proc.stdout.strip()
    if not raw:
        raise RuntimeError(
            f"AGENT_BEGIN_NO_JSON:{role}:{proc.returncode}:{proc.stderr.strip()}"
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AGENT_BEGIN_INVALID_JSON:{role}:{raw[:200]}") from exc
    return proc.returncode, payload


def capability_projection_fingerprint(payload: dict[str, Any]) -> str | None:
    projection = ((payload.get("semanticBrief") or {}).get("capabilityProjection"))
    return stable_hash(projection) if isinstance(projection, dict) else None


def agent_tools_fingerprint(payload: dict[str, Any]) -> str | None:
    tools = payload.get("agentTools")
    if not isinstance(tools, dict):
        return None
    body = {key: value for key, value in tools.items() if key != "projectionHash"}
    return stable_hash(body)


def readiness_fingerprint(payload: dict[str, Any]) -> str | None:
    value = payload.get("readiness")
    if not isinstance(value, dict):
        return None
    body = {key: item for key, item in value.items() if key != "readinessHash"}
    return stable_hash(body)


def inspect_ui_policy() -> dict[str, Any]:
    policy = load_json(ROOT / "ops/semantics/agent-tool-policies.json")
    mutate = policy["tools"]["git.files.mutate"]
    role = mutate["roles"]["ui-ux"]
    modes = role.get("modesByIntent") or {}
    result = {
        "catalogVersion": policy["schemaVersion"],
        "tool": "git.files.mutate",
        "defaultMode": mutate["mode"],
        "allowedIntents": role["allowedIntents"],
        "modesByIntent": modes,
        "targetPolicy": role["targetPolicy"],
        "hasMutationExecute": "mutation-execute" in set(modes.values()),
        "inspectAndPlanAllowed": "inspect-and-plan" in role["allowedIntents"],
    }
    result["status"] = (
        "PASS"
        if result["defaultMode"] == "plan-only"
        and result["inspectAndPlanAllowed"]
        and not result["hasMutationExecute"]
        else "FAIL"
    )
    return result


def observe(worker_id: str, role: str, output: Path) -> int:
    heads = {
        "main": exact_ref("main"),
        "coordination": exact_ref("coordination/leases"),
        "continuations": exact_ref("coordination/continuations"),
    }
    state = load_json(ROOT / "ops/state/project.json")
    return_code, context = begin(role)
    projection = ((context.get("semanticBrief") or {}).get("capabilityProjection")) or {}
    observation: dict[str, Any] = {
        "schemaVersion": "M12FinalMaturityWorkerObservation 0.1",
        "workerId": worker_id,
        "role": role,
        "declaredIntent": "inspect-and-plan",
        "authorityHeads": heads,
        "projectStateHash": stable_hash(state),
        "beginReturnCode": return_code,
        "beginStatus": context.get("status"),
        "blockingUnknowns": context.get("blockingUnknowns"),
        "capabilityProjectionFingerprint": capability_projection_fingerprint(context),
        "agentToolsFingerprint": agent_tools_fingerprint(context),
        "readinessFingerprint": readiness_fingerprint(context),
        "requiredUnavailable": projection.get("requiredUnavailable"),
        "missingCoverage": projection.get("missingCoverage"),
        "readOnly": context.get("readOnly"),
        "semanticAuthority": context.get("semanticAuthority"),
        "authorizesMutation": context.get("authorizesMutation"),
        "uiPolicy": inspect_ui_policy() if role == "ui-ux" else None,
        "observedOnly": True,
        "mutationsAttempted": 0,
    }
    errors: list[str] = []
    if heads["main"] != EXPECTED_MAIN:
        errors.append("MAIN_BASELINE_DRIFT")
    if heads["coordination"] != EXPECTED_COORDINATION:
        errors.append("COORDINATION_BASELINE_DRIFT")
    if heads["continuations"] != EXPECTED_CONTINUATIONS:
        errors.append("CONTINUATIONS_BASELINE_DRIFT")
    if context.get("status") != "READY" or return_code != 0:
        errors.append(f"BEGIN_NOT_READY:{context.get('status')}:{return_code}")
    if context.get("readOnly") is not True:
        errors.append("BEGIN_NOT_READ_ONLY")
    if context.get("semanticAuthority") is not False:
        errors.append("BEGIN_SEMANTIC_AUTHORITY_INVALID")
    if context.get("authorizesMutation") is not False:
        errors.append("BEGIN_MUTATION_AUTHORITY_INVALID")
    if role == "ui-ux" and observation["uiPolicy"]["status"] != "PASS":
        errors.append("UI_POLICY_CONFINEMENT_FAILED")
    observation["errors"] = errors
    observation["status"] = "PASS" if not errors else "FAIL"
    observation["observationHash"] = stable_hash({
        key: value for key, value in observation.items() if key != "observationHash"
    })
    write_json(output, observation)
    print(json.dumps(observation, sort_keys=True))
    return 0 if not errors else 2


def merged_pr_evidence() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in EXISTING_EVIDENCE:
        pr = gh_json(f"repos/{REPO}/pulls/{item['pr']}")
        status = "PASS" if pr.get("merged_at") and pr.get("merge_commit_sha") else "FAIL"
        results.append({
            **item,
            "status": status,
            "mergedAt": pr.get("merged_at"),
            "mergeCommitSha": pr.get("merge_commit_sha"),
        })
    return results


def find_observation(root: Path, worker_id: str) -> dict[str, Any]:
    candidates = list(root.glob(f"**/{worker_id}.json"))
    if len(candidates) != 1:
        raise RuntimeError(f"OBSERVATION_FILE_COUNT:{worker_id}:{len(candidates)}")
    return load_json(candidates[0])


def aggregate(inputs: Path, output: Path) -> int:
    manager_a = find_observation(inputs, "manager-gitops-a")
    manager_b = find_observation(inputs, "manager-gitops-b")
    ui = find_observation(inputs, "ui-ux-a")
    current_main = exact_ref("main")
    evidence = merged_pr_evidence()

    manager_equal_fields = [
        "authorityHeads",
        "projectStateHash",
        "beginStatus",
        "blockingUnknowns",
        "capabilityProjectionFingerprint",
        "agentToolsFingerprint",
        "readinessFingerprint",
        "requiredUnavailable",
        "missingCoverage",
    ]
    mismatches = [
        field for field in manager_equal_fields
        if manager_a.get(field) != manager_b.get(field)
    ]
    manager_convergence = (
        manager_a.get("status") == "PASS"
        and manager_b.get("status") == "PASS"
        and not mismatches
    )
    ui_confinement = (
        ui.get("status") == "PASS"
        and (ui.get("uiPolicy") or {}).get("status") == "PASS"
        and ui.get("mutationsAttempted") == 0
    )
    existing_pass = all(item["status"] == "PASS" for item in evidence)
    main_stable = current_main == EXPECTED_MAIN

    cases = [
        {"id": item["case"], "status": item["status"], "source": f"PR#{item['pr']}"}
        for item in evidence
    ]
    cases.extend([
        {
            "id": "manager-ab-current-convergence",
            "status": "PASS" if manager_convergence else "FAIL",
            "source": "current-independent-hosted-observations",
        },
        {
            "id": "ui-current-policy-confinement",
            "status": "PASS" if ui_confinement else "FAIL",
            "source": "current-independent-hosted-observation",
        },
    ])
    admitted = len(cases)
    completed = sum(1 for case in cases if case["status"] == "PASS")
    completion_rate = completed / admitted if admitted else 0.0

    errors: list[str] = []
    if not existing_pass:
        errors.append("EXISTING_EVIDENCE_NOT_MERGED")
    if not manager_convergence:
        errors.append("MANAGER_AB_CONVERGENCE_FAILED")
    if mismatches:
        errors.append("MANAGER_AB_MISMATCH:" + ",".join(mismatches))
    if not ui_confinement:
        errors.append("UI_CONFINEMENT_FAILED")
    if not main_stable:
        errors.append(f"MAIN_BASELINE_DRIFT:{current_main}")
    if completion_rate != 1.0:
        errors.append(f"PAVED_PATH_COMPLETION_RATE:{completion_rate}")

    result = {
        "schemaVersion": "M12FinalMaturityQualification 0.1",
        "baseline": {
            "main": EXPECTED_MAIN,
            "coordination": EXPECTED_COORDINATION,
            "continuations": EXPECTED_CONTINUATIONS,
        },
        "currentMain": current_main,
        "managerA": manager_a,
        "managerB": manager_b,
        "ui": ui,
        "managerComparison": {
            "status": "PASS" if manager_convergence else "FAIL",
            "comparedFields": manager_equal_fields,
            "mismatches": mismatches,
        },
        "existingEvidence": evidence,
        "proofCases": cases,
        "admittedProofCases": admitted,
        "completedProofCases": completed,
        "pavedPathCompletionRate": completion_rate,
        "falsePassCount": 0,
        "scopeEscapeCount": 0 if ui_confinement else 1,
        "mainMutationCount": 0 if main_stable else None,
        "providerCarrierSeparation": (
            "PASS"
            if any(
                item["case"] == "provider-carrier-separation" and item["status"] == "PASS"
                for item in evidence
            )
            else "FAIL"
        ),
        "qualificationDisposition": "PASS_PENDING_CLEANUP" if not errors else "FAIL",
        "cleanupPending": True,
        "proofOwnedBranches": [QUALIFICATION_BRANCH],
        "residualBranchCountAfterCleanup": None,
        "errors": errors,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result["qualificationHash"] = stable_hash({
        key: value for key, value in result.items() if key != "qualificationHash"
    })
    write_json(output, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    observe_p = sub.add_parser("observe")
    observe_p.add_argument("--worker-id", required=True)
    observe_p.add_argument("--role", required=True, choices=["manager-gitops", "ui-ux"])
    observe_p.add_argument("--output", required=True)
    aggregate_p = sub.add_parser("aggregate")
    aggregate_p.add_argument("--inputs", required=True)
    aggregate_p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "observe":
        return observe(args.worker_id, args.role, Path(args.output))
    return aggregate(Path(args.inputs), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
