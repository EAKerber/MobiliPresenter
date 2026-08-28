from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from tools import agent_failure, hosted_cycle_handle
from tools.canonical import stable_hash

PROJECTION_SCHEMA = "HostedCycleArtifactResumability 0.1"
BEGIN_RESULT_SCHEMA = "HostedAgentCycleBeginResult 0.5"
LEGACY_BEGIN_RESULT_SCHEMA = "HostedAgentCycleBeginResult 0.4"
PROVIDER = "github-actions-artifact"
STATES = {"AVAILABLE", "EXPIRED", "MISSING", "AMBIGUOUS", "MISMATCH", "UNKNOWN"}
PROJECTION_FIELDS = {
    "schemaVersion", "state", "provider", "runId", "artifactName", "artifactId",
    "headSha", "expiresAt", "reasonCodes", "readOnly", "semanticAuthority",
    "authorizesMutation", "projectionHash",
}

STATE_CODES = {
    "EXPIRED": "HOSTED_AGENT_BEGIN_ARTIFACT_EXPIRED",
    "MISSING": "HOSTED_AGENT_BEGIN_ARTIFACT_MISSING",
    "AMBIGUOUS": "HOSTED_AGENT_BEGIN_ARTIFACT_AMBIGUOUS",
    "MISMATCH": "HOSTED_AGENT_BEGIN_ARTIFACT_MISMATCH",
    "UNKNOWN": "HOSTED_AGENT_BEGIN_ARTIFACT_OBSERVATION_UNKNOWN",
}


class HostedCycleArtifactError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleArtifactError(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise HostedCycleArtifactError(code)
    return value


def _projection(
    *,
    state: str,
    run_id: int,
    artifact_name: str,
    artifact_id: int | None = None,
    head_sha: str | None = None,
    expires_at: str | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    if state not in STATES:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_STATE_INVALID")
    run_id = _positive_int(run_id, "HOSTED_CYCLE_ARTIFACT_RUN_INVALID")
    artifact_name = _text(artifact_name, "HOSTED_CYCLE_ARTIFACT_NAME_INVALID")
    reasons = sorted(set(reason_codes or []))
    if any(not isinstance(item, str) or not item for item in reasons):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_REASON_INVALID")
    if artifact_id is not None:
        artifact_id = _positive_int(artifact_id, "HOSTED_CYCLE_ARTIFACT_ID_INVALID")
    if head_sha is not None:
        head_sha = _text(head_sha, "HOSTED_CYCLE_ARTIFACT_HEAD_INVALID")
    if expires_at is not None:
        expires_at = _text(expires_at, "HOSTED_CYCLE_ARTIFACT_EXPIRY_INVALID")
    core = {
        "schemaVersion": PROJECTION_SCHEMA,
        "state": state,
        "provider": PROVIDER,
        "runId": run_id,
        "artifactName": artifact_name,
        "artifactId": artifact_id,
        "headSha": head_sha,
        "expiresAt": expires_at,
        "reasonCodes": reasons,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "projectionHash": stable_hash(core)}


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PROJECTION_FIELDS:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    if value.get("schemaVersion") != PROJECTION_SCHEMA or value.get("state") not in STATES:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    if value.get("provider") != PROVIDER:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_PROVIDER_INVALID")
    _positive_int(value.get("runId"), "HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    _text(value.get("artifactName"), "HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    if value.get("artifactId") is not None:
        _positive_int(value["artifactId"], "HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    for key in ("headSha", "expiresAt"):
        if value.get(key) is not None:
            _text(value[key], "HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    reasons = value.get("reasonCodes")
    if (
        not isinstance(reasons, list)
        or reasons != sorted(set(reasons))
        or any(not isinstance(item, str) or not item for item in reasons)
    ):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_PROJECTION_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_BOUNDARY_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "projectionHash"}
    if value.get("projectionHash") != stable_hash(core):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_PROJECTION_HASH_MISMATCH")
    return value


def classify_artifact_response(
    response: Any,
    *,
    run_id: int,
    artifact_name: str,
    source_sha: str,
) -> dict[str, Any]:
    run_id = _positive_int(run_id, "HOSTED_CYCLE_ARTIFACT_RUN_INVALID")
    artifact_name = _text(artifact_name, "HOSTED_CYCLE_ARTIFACT_NAME_INVALID")
    source_sha = _text(source_sha, "HOSTED_CYCLE_ARTIFACT_SOURCE_INVALID")
    if not isinstance(response, dict) or not isinstance(response.get("artifacts"), list):
        return _projection(
            state="UNKNOWN", run_id=run_id, artifact_name=artifact_name,
            reason_codes=["HOSTED_AGENT_BEGIN_ARTIFACT_METADATA_INVALID"],
        )
    artifacts = response["artifacts"]
    total = response.get("total_count")
    if (
        total is not None
        and (not isinstance(total, int) or isinstance(total, bool) or total < 0 or total > len(artifacts))
    ):
        return _projection(
            state="UNKNOWN", run_id=run_id, artifact_name=artifact_name,
            reason_codes=["HOSTED_AGENT_BEGIN_ARTIFACT_LIST_INCOMPLETE"],
        )
    matches = [item for item in artifacts if isinstance(item, dict) and item.get("name") == artifact_name]
    if not matches:
        return _projection(
            state="MISSING", run_id=run_id, artifact_name=artifact_name,
            reason_codes=[STATE_CODES["MISSING"]],
        )
    if len(matches) != 1:
        return _projection(
            state="AMBIGUOUS", run_id=run_id, artifact_name=artifact_name,
            reason_codes=[STATE_CODES["AMBIGUOUS"]],
        )
    artifact = matches[0]
    artifact_id = artifact.get("id")
    expired = artifact.get("expired")
    expires_at = artifact.get("expires_at")
    workflow_run = artifact.get("workflow_run")
    if (
        not isinstance(artifact_id, int)
        or isinstance(artifact_id, bool)
        or artifact_id <= 0
        or not isinstance(expired, bool)
        or not isinstance(expires_at, str)
        or not expires_at
        or not isinstance(workflow_run, dict)
    ):
        return _projection(
            state="UNKNOWN", run_id=run_id, artifact_name=artifact_name,
            reason_codes=["HOSTED_AGENT_BEGIN_ARTIFACT_METADATA_INVALID"],
        )
    observed_run = workflow_run.get("id")
    head_sha = workflow_run.get("head_sha")
    if observed_run != run_id or head_sha != source_sha:
        return _projection(
            state="MISMATCH", run_id=run_id, artifact_name=artifact_name,
            artifact_id=artifact_id,
            head_sha=head_sha if isinstance(head_sha, str) and head_sha else None,
            expires_at=expires_at,
            reason_codes=[STATE_CODES["MISMATCH"]],
        )
    return _projection(
        state="EXPIRED" if expired else "AVAILABLE",
        run_id=run_id,
        artifact_name=artifact_name,
        artifact_id=artifact_id,
        head_sha=head_sha,
        expires_at=expires_at,
        reason_codes=[] if not expired else [STATE_CODES["EXPIRED"]],
    )


def _gh_artifacts(repository: str, run_id: int) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "gh", "api",
            f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise HostedCycleArtifactError("HOSTED_AGENT_BEGIN_ARTIFACT_OBSERVATION_FAILED")
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HostedCycleArtifactError("HOSTED_AGENT_BEGIN_ARTIFACT_METADATA_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedCycleArtifactError("HOSTED_AGENT_BEGIN_ARTIFACT_METADATA_INVALID")
    return value


def observe_begin_artifact(
    *,
    repository: str,
    run_id: int,
    source_sha: str,
    artifact_name: str | None = None,
) -> dict[str, Any]:
    name = artifact_name or f"agent-cycle-begin-{run_id}"
    try:
        response = _gh_artifacts(repository, run_id)
    except HostedCycleArtifactError as exc:
        return _projection(
            state="UNKNOWN", run_id=run_id, artifact_name=name,
            reason_codes=[exc.code],
        )
    return classify_artifact_response(
        response,
        run_id=run_id,
        artifact_name=name,
        source_sha=source_sha,
    )


def _validate_hash_bound(value: dict[str, Any], *, hash_field: str) -> None:
    digest = value.get(hash_field)
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != hash_field}
    if not isinstance(digest, str) or digest != stable_hash(core):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_RESULT_HASH_INVALID")


def finalize_begin_result(
    result: dict[str, Any],
    manifest: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    observation = validate_projection(observation)
    if observation["state"] != "AVAILABLE":
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_BEGIN_NOT_RESUMABLE")
    if not isinstance(result, dict) or result.get("status") != "READY":
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_BEGIN_RESULT_INVALID")
    _validate_hash_bound(result, hash_field="resultHash")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("source"), dict):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_MANIFEST_INVALID")
    source = manifest["source"]
    expected = {
        "runId": source.get("runId"),
        "sourceSha": source.get("sourceSha"),
        "artifactName": manifest.get("artifactName"),
        "cycleId": manifest.get("cycleId"),
        "cycleInstanceId": manifest.get("cycleInstanceId"),
        "contextHash": manifest.get("contextHash"),
    }
    if any(result.get(key) != item for key, item in expected.items()):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_BEGIN_RESULT_BINDING_MISMATCH")
    try:
        _, locator = hosted_cycle_handle.decode_handle(result.get("handle"))
    except RuntimeError as exc:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_HANDLE_INVALID") from exc
    if (
        locator["runId"] != observation["runId"]
        or locator["sourceSha"] != observation["headSha"]
        or locator["artifactName"] != observation["artifactName"]
    ):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_HANDLE_BINDING_MISMATCH")
    if result.get("schemaVersion") == BEGIN_RESULT_SCHEMA:
        if result.get("resumability") != observation:
            raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_RESUMABILITY_DRIFT")
        return result
    if result.get("schemaVersion") != LEGACY_BEGIN_RESULT_SCHEMA or "resumability" in result:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_BEGIN_RESULT_SCHEMA_UNSUPPORTED")
    core = {
        key: copy.deepcopy(item)
        for key, item in result.items()
        if key != "resultHash"
    }
    core["schemaVersion"] = BEGIN_RESULT_SCHEMA
    core["resumability"] = copy.deepcopy(observation)
    return {**core, "resultHash": stable_hash(core)}


def failure_code(observation: dict[str, Any]) -> str | None:
    value = validate_projection(observation)
    if value["state"] == "AVAILABLE":
        return None
    if value["reasonCodes"]:
        return value["reasonCodes"][0]
    return STATE_CODES.get(value["state"], "HOSTED_AGENT_BEGIN_ARTIFACT_OBSERVATION_UNKNOWN")


def failure_for_observation(
    command: dict[str, Any],
    observation: dict[str, Any],
    *,
    download_failed: bool = False,
) -> dict[str, Any]:
    from tools import hosted_agent_cycle

    value = validate_projection(observation)
    code = failure_code(value) or "HOSTED_AGENT_BEGIN_ARTIFACT_UNAVAILABLE"
    semantic_status = "BLOCKED"
    observation_retry = "NOT_APPLICABLE"
    if value["state"] == "UNKNOWN":
        semantic_status = "UNKNOWN"
        observation_retry = "SAFE"
    elif value["state"] == "MISSING":
        observation_retry = "SAFE"
    if download_failed and value["state"] == "AVAILABLE":
        code = "HOSTED_AGENT_BEGIN_ARTIFACT_DOWNLOAD_UNKNOWN"
        semantic_status = "UNKNOWN"
        observation_retry = "SAFE"
    core = agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase="TRANSPORT",
        status=semantic_status,
        causes=[{"code": code, "source": "hosted-cycle-artifact", "phase": "TRANSPORT"}],
        observation_retry=observation_retry,
        operation_replay="NOT_APPLICABLE",
        mutation_state="NOT_APPLICABLE",
        lossy_projection=False,
    )
    hosted_agent_cycle.validate_transport_command(command)
    body = {
        "schemaVersion": agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA,
        "requestId": command.get("requestId"),
        "commandHash": hosted_agent_cycle.transport_command_hash(command),
        "status": "BLOCKED",
        "failureCore": core,
    }
    result = {**body, "failureHash": stable_hash(body)}
    return agent_failure.validate_hosted_cycle_failure(result)


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_FILE_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_FILE_INVALID")
    return value


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def qualify_begin_files(
    *,
    repository: str,
    command_path: str | Path,
    manifest_path: str | Path,
    result_path: str | Path,
    observation_path: str | Path,
) -> bool:
    command = _load(command_path)
    manifest = _load(manifest_path)
    result = _load(result_path)
    source = manifest.get("source") if isinstance(manifest, dict) else None
    if not isinstance(source, dict):
        raise HostedCycleArtifactError("HOSTED_CYCLE_ARTIFACT_MANIFEST_INVALID")
    observation = observe_begin_artifact(
        repository=repository,
        run_id=source.get("runId"),
        source_sha=source.get("sourceSha"),
        artifact_name=manifest.get("artifactName"),
    )
    _write(observation_path, observation)
    if observation["state"] == "AVAILABLE":
        _write(result_path, finalize_begin_result(result, manifest, observation))
        return True
    _write(result_path, failure_for_observation(command, observation))
    return False


def qualify_close_files(
    *,
    repository: str,
    command_path: str | Path,
    run_id: int,
    source_sha: str,
    result_path: str | Path,
    observation_path: str | Path,
    download_failed: bool = False,
) -> bool:
    command = _load(command_path)
    observation = observe_begin_artifact(
        repository=repository,
        run_id=run_id,
        source_sha=source_sha,
    )
    _write(observation_path, observation)
    if observation["state"] == "AVAILABLE" and not download_failed:
        return True
    _write(
        result_path,
        failure_for_observation(command, observation, download_failed=download_failed),
    )
    return False
