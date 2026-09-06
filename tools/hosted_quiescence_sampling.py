from __future__ import annotations

import copy
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools import (
    agent_cycle,
    operational_quiescence,
    project_machine,
    reflection_eligibility,
    scheduler_snapshot,
)

APPLICABLE_ROLE = "manager-gitops"
APPLICABLE_INTENT = "inspect-and-plan"
HOSTED_WORKFLOW = "hosted-agent-cycle.yml"
HISTORY_SAMPLE_LIMIT = operational_quiescence.WINDOW_SIZE - 1
HISTORY_STEP_NAME = "Derive hosted quiescence sample"


class HostedQuiescenceHistoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("HOSTED_QUIESCENCE_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("HOSTED_QUIESCENCE_INPUT_INVALID")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _slot(context: dict[str, Any], name: str) -> dict[str, Any]:
    slot = context.get(name)
    if (
        not isinstance(slot, dict)
        or slot.get("status") != "PASS"
        or not isinstance(slot.get("value"), dict)
    ):
        raise RuntimeError(f"HOSTED_QUIESCENCE_{name.upper()}_UNAVAILABLE")
    return copy.deepcopy(slot["value"])


def is_applicable(context: dict[str, Any]) -> bool:
    agent_cycle.validate_context(context)
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict):
        raise RuntimeError("HOSTED_QUIESCENCE_SEMANTIC_CONTEXT_INVALID")
    return (
        semantic.get("role") == APPLICABLE_ROLE
        and semantic.get("declaredIntent") == APPLICABLE_INTENT
    )


def build_snapshot_from_context(context: dict[str, Any]) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        raise RuntimeError("HOSTED_QUIESCENCE_NOT_APPLICABLE")
    source_machine = copy.deepcopy(context["projectMachine"])
    routine = _slot(context, "routineInspection")
    maintenance = _slot(context, "maintenanceInspection")
    plan = _slot(context, "schedulerPlan")
    return scheduler_snapshot.build_snapshot(
        source_machine,
        routine,
        maintenance,
        plan,
    )


def derive_sample(
    context: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    readback_machine: dict[str, Any],
    observation_id: str,
    sequence: int,
) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        raise RuntimeError("HOSTED_QUIESCENCE_NOT_APPLICABLE")
    source_machine = copy.deepcopy(context["projectMachine"])
    routine = _slot(context, "routineInspection")
    scheduler_snapshot.validate_snapshot(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
    )
    reflection = reflection_eligibility.build_inspection(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
    )
    sample = operational_quiescence.build_sample(
        snapshot=snapshot,
        reflection=reflection,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
        observation_id=observation_id,
        sequence=sequence,
    )
    return {
        "snapshot": snapshot,
        "readbackMachine": copy.deepcopy(readback_machine),
        "reflectionEligibility": reflection,
        "sample": sample,
    }


def materialize(
    context: dict[str, Any],
    *,
    observation_id: str,
    sequence: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        return {
            "ok": True,
            "applicable": False,
            "role": context["semanticContext"]["role"],
            "declaredIntent": context["semanticContext"]["declaredIntent"],
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Preserve the same trust boundary as Supervisor Snapshot:
    # source-derived immutable snapshot first, then a fresh live readback.
    snapshot = build_snapshot_from_context(context)
    _write_json(root / "scheduler-snapshot.json", snapshot)

    readback = project_machine.inspect_live()
    _write_json(root / "project-machine-readback.json", readback)

    derived = derive_sample(
        context,
        snapshot=snapshot,
        readback_machine=readback,
        observation_id=observation_id,
        sequence=sequence,
    )
    _write_json(root / "reflection-eligibility.json", derived["reflectionEligibility"])
    _write_json(root / "operational-quiescence-sample.json", derived["sample"])

    sample = derived["sample"]
    return {
        "ok": True,
        "applicable": True,
        "sampleHash": sample["sampleHash"],
        "sampleEligible": sample["sampleEligible"],
        "reflectionStatus": sample["reflectionStatus"],
        "baselineHash": sample["baselineHash"],
        "observationId": sample["observationId"],
        "sequence": sample["sequence"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _gh_json(repository: str, endpoint: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["gh", "api", endpoint],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_OBSERVATION_FAILED")
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_METADATA_INVALID"
        ) from exc
    if not isinstance(value, dict):
        raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_METADATA_INVALID")
    return value


def _workflow_runs(repository: str) -> list[dict[str, Any]]:
    value = _gh_json(
        repository,
        f"repos/{repository}/actions/workflows/{HOSTED_WORKFLOW}/runs?per_page=100",
    )
    runs = value.get("workflow_runs")
    if not isinstance(runs, list):
        raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_RUNS_INVALID")
    out: list[dict[str, Any]] = []
    for item in runs:
        if not isinstance(item, dict):
            raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_RUN_INVALID")
        run_id = item.get("id")
        run_number = item.get("run_number")
        run_attempt = item.get("run_attempt")
        if (
            not isinstance(run_id, int)
            or isinstance(run_id, bool)
            or run_id <= 0
            or not isinstance(run_number, int)
            or isinstance(run_number, bool)
            or run_number <= 0
            or not isinstance(run_attempt, int)
            or isinstance(run_attempt, bool)
            or run_attempt <= 0
        ):
            raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_RUN_INVALID")
        out.append(copy.deepcopy(item))
    return out


def _sample_step_conclusion(repository: str, run_id: int) -> str:
    value = _gh_json(
        repository,
        f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
    )
    jobs = value.get("jobs")
    if not isinstance(jobs, list):
        raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_JOBS_INVALID")
    for job in jobs:
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and step.get("name") == HISTORY_STEP_NAME:
                conclusion = step.get("conclusion")
                if not isinstance(conclusion, str) or not conclusion:
                    raise HostedQuiescenceHistoryError(
                        "HOSTED_QUIESCENCE_HISTORY_STEP_UNKNOWN"
                    )
                return conclusion
    raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_STEP_UNKNOWN")


def _artifact_for_run(
    repository: str,
    *,
    run_id: int,
    head_sha: str,
) -> dict[str, Any] | None:
    value = _gh_json(
        repository,
        f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
    )
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_ARTIFACTS_INVALID"
        )
    total = value.get("total_count")
    if (
        total is not None
        and (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < 0
            or total > len(artifacts)
        )
    ):
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_ARTIFACT_LIST_INCOMPLETE"
        )
    name = f"hosted-quiescence-{run_id}"
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("name") == name
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_ARTIFACT_AMBIGUOUS"
        )
    artifact = matches[0]
    workflow_run = artifact.get("workflow_run")
    artifact_id = artifact.get("id")
    if (
        not isinstance(artifact_id, int)
        or isinstance(artifact_id, bool)
        or artifact_id <= 0
        or artifact.get("expired") is not False
        or not isinstance(workflow_run, dict)
        or workflow_run.get("id") != run_id
        or workflow_run.get("head_sha") != head_sha
    ):
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_ARTIFACT_INVALID"
        )
    return copy.deepcopy(artifact)


def _download_sample_from_run(
    repository: str,
    run: dict[str, Any],
) -> dict[str, Any] | None:
    run_id = int(run["id"])
    head_sha = run.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise HostedQuiescenceHistoryError("HOSTED_QUIESCENCE_HISTORY_RUN_HEAD_INVALID")
    artifact = _artifact_for_run(
        repository,
        run_id=run_id,
        head_sha=head_sha,
    )
    if artifact is None:
        conclusion = _sample_step_conclusion(repository, run_id)
        if conclusion == "skipped":
            return None
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_ARTIFACT_MISSING"
        )

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "-R",
                repository,
                "-n",
                artifact["name"],
                "-D",
                tmp,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_ARTIFACT_DOWNLOAD_FAILED"
            )
        root = Path(tmp)
        result_path = root / "result.json"
        if not result_path.is_file():
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_RESULT_MISSING"
            )
        try:
            result = _load_json(result_path)
        except RuntimeError as exc:
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_RESULT_INVALID"
            ) from exc
        if result.get("ok") is not True:
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_SAMPLE_UNKNOWN"
            )
        if result.get("applicable") is False:
            return None
        if result.get("applicable") is not True:
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_RESULT_INVALID"
            )
        sample_path = root / "operational-quiescence-sample.json"
        if not sample_path.is_file():
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_SAMPLE_MISSING"
            )
        try:
            sample = _load_json(sample_path)
            operational_quiescence.validate_sample(sample)
        except RuntimeError as exc:
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_SAMPLE_INVALID"
            ) from exc

    expected_observation = f"{run_id}:{run['run_attempt']}"
    if (
        sample["observationId"] != expected_observation
        or sample["sequence"] != run["run_number"]
    ):
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_CARRIER_MISMATCH"
        )
    return sample


def collect_prior_samples(
    *,
    repository: str,
    current_run_id: int,
    current_sequence: int,
) -> list[dict[str, Any]]:
    runs = sorted(
        _workflow_runs(repository),
        key=lambda item: int(item["run_number"]),
        reverse=True,
    )
    samples: list[dict[str, Any]] = []
    for run in runs:
        run_id = int(run["id"])
        run_number = int(run["run_number"])
        if run_id == current_run_id or run_number >= current_sequence:
            continue
        if run.get("status") != "completed":
            raise HostedQuiescenceHistoryError(
                "HOSTED_QUIESCENCE_HISTORY_CONCURRENT_RUN"
            )
        sample = _download_sample_from_run(repository, run)
        if sample is None:
            continue
        samples.append(sample)
        if len(samples) >= HISTORY_SAMPLE_LIMIT:
            break
    return sorted(samples, key=lambda item: int(item["sequence"]))


def _run_id_from_observation_id(observation_id: str) -> int:
    if not isinstance(observation_id, str):
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_OBSERVATION_ID_INVALID"
        )
    prefix, separator, _attempt = observation_id.partition(":")
    if not separator or not prefix.isdigit():
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_OBSERVATION_ID_INVALID"
        )
    value = int(prefix)
    if value <= 0:
        raise HostedQuiescenceHistoryError(
            "HOSTED_QUIESCENCE_HISTORY_OBSERVATION_ID_INVALID"
        )
    return value


def materialize_window(
    current_sample: dict[str, Any],
    *,
    output_dir: str | Path,
    repository: str = operational_quiescence.REPOSITORY,
) -> dict[str, Any]:
    operational_quiescence.validate_sample(current_sample)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    history_status = "AVAILABLE"
    history_reasons: list[str] = []
    try:
        prior = collect_prior_samples(
            repository=repository,
            current_run_id=_run_id_from_observation_id(
                current_sample["observationId"]
            ),
            current_sequence=current_sample["sequence"],
        )
    except HostedQuiescenceHistoryError as exc:
        prior = []
        history_status = "UNKNOWN"
        history_reasons = [exc.code]

    samples = [*prior, copy.deepcopy(current_sample)]
    window = operational_quiescence.evaluate_window(samples)
    _write_json(root / "operational-quiescence.json", window)
    return {
        "historyStatus": history_status,
        "historyReasonCodes": history_reasons,
        "historySampleCount": len(prior),
        "windowStatus": window["status"],
        "windowComplete": window["windowComplete"],
        "windowEligible": window["eligible"],
        "windowEvaluationHash": window["evaluationHash"],
    }


def materialize_from_files(
    *,
    context_path: str | Path,
    observation_id: str,
    sequence: int,
    output_dir: str | Path,
) -> int:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        result = materialize(
            _load_json(context_path),
            observation_id=observation_id,
            sequence=sequence,
            output_dir=root,
        )
        if result.get("applicable") is True:
            sample = _load_json(root / "operational-quiescence-sample.json")
            result = {
                **result,
                **materialize_window(sample, output_dir=root),
            }
        rc = 0
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        result = {
            "ok": False,
            "error": str(exc),
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        rc = 2
    _write_json(root / "result.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return rc
