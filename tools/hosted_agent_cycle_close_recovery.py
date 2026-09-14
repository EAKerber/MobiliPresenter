#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools import agent_cycle_close
from tools import agent_cycle_close_recovery
from tools import agent_failure
from tools import hosted_agent_cycle as hosted

EXACT_CAUSES = [
    {"code": "UNATTRIBUTED_DURABLE_DELTA", "source": "agent-cycle-close", "phase": "CLOSE"},
    {"code": "HOSTED_AGENT_CLOSE_NOT_PASS", "source": "hosted-agent-cycle", "phase": "CLOSE"},
]


def _load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _exact_core(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    recovery = value.get("recovery")
    return (
        value.get("schemaVersion") == "AgentFailureCore 0.1"
        and value.get("surface") == "AGENT_CYCLE"
        and value.get("phase") == "CLOSE"
        and value.get("status") == "UNKNOWN"
        and value.get("causes") == EXACT_CAUSES
        and isinstance(recovery, dict)
        and recovery.get("observationRetry") == "UNKNOWN"
        and recovery.get("operationReplay") == "NOT_APPLICABLE"
        and value.get("mutationState") == "NOT_APPLICABLE"
        and value.get("lossyProjection") is False
        and value.get("readOnly") is True
        and value.get("semanticAuthority") is False
        and value.get("authorizesMutation") is False
    )


def _compatibility_source_allows(path: Path, command: dict[str, Any]) -> bool:
    if not path.is_file():
        return False
    try:
        value = agent_failure.validate_hosted_cycle_failure(_load(path))
    except Exception:
        return False
    return (
        value.get("schemaVersion") == "HostedAgentCycleFailure 0.2"
        and value.get("requestId") == command.get("requestId")
        and value.get("commandHash") == hosted.transport_command_hash(command)
        and value.get("status") == "BLOCKED"
        and _exact_core(value.get("failureCore"))
    )


def _hosted_close_result(*, command: dict[str, Any], meta: dict[str, int], manifest: dict[str, Any], closure: dict[str, Any]) -> dict[str, Any]:
    source = hosted._source(meta)
    receipt = closure["receipt"]
    core = {
        "schemaVersion": hosted.CLOSE_RESULT_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted.transport_command_hash(command),
        "runId": source["runId"],
        "sourceSha": source["sourceSha"],
        "beginRunId": manifest["source"]["runId"],
        "cycleId": closure["cycleId"],
        "contextHash": manifest["contextHash"],
        "receiptHash": receipt["receiptHash"],
        "closureHash": closure["closureHash"],
        "status": "PASS",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": hosted.stable_hash(core)}


def close_with_compatibility_recovery(command: dict[str, Any], meta: dict[str, int], *, begin_dir: str, output_path: str, evidence_dir: str) -> dict[str, Any]:
    outer = hosted.validate_transport_command(command)
    try:
        return hosted.close_from_envelope(outer, meta, begin_dir=begin_dir, output_path=output_path, evidence_dir=evidence_dir)
    except hosted.HostedAgentCycleError as exc:
        original = exc

    if original.code != "HOSTED_AGENT_CLOSE_NOT_PASS" or not _exact_core(original.failure_core):
        raise original
    close_root = Path(output_path).parent
    if not _compatibility_source_allows(close_root / "compatibility-recovery-source.json", outer):
        raise original

    try:
        closure = _load(output_path)
        context_path = str(Path(begin_dir) / "context.json")
        evidence_root = Path(evidence_dir)
        evidence_paths = sorted(str(path) for path in evidence_root.glob("evidence-*.json"))
        recovery_path = evidence_root / "evidence-recovery-merge.json"
        recovered = agent_cycle_close_recovery.recover_closure(
            closure,
            context_path=context_path,
            machine_scope="live",
            observations_path=None,
            runtime_providers=None,
            evidence_paths=evidence_paths,
            recovery_evidence_path=str(recovery_path),
        )
        if recovered.get("status") != "PASS" or not recovery_path.is_file():
            raise original
        full_evidence = agent_cycle_close.load_evidence([*evidence_paths, str(recovery_path)])
        context = _load(context_path)
        agent_cycle_close.validate_closure(recovered, context, evidence=full_evidence)
        manifest = _load(Path(begin_dir) / "manifest.json")
        _write(output_path, recovered)
        return _hosted_close_result(command=outer, meta=meta, manifest=manifest, closure=recovered)
    except hosted.HostedAgentCycleError:
        raise
    except Exception:
        raise original


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-agent-cycle-close-recovery")
    sub = parser.add_subparsers(dest="command_name", required=True)
    close = sub.add_parser("close")
    close.add_argument("--command", required=True)
    close.add_argument("--meta", required=True)
    close.add_argument("--begin-dir", required=True)
    close.add_argument("--closure", required=True)
    close.add_argument("--evidence-dir", required=True)
    close.add_argument("--result", required=True)
    args = parser.parse_args(argv)

    command_value: dict[str, Any] | None = None
    try:
        command_value = _load(args.command)
        meta = _load(args.meta)
        result = close_with_compatibility_recovery(command_value, meta, begin_dir=args.begin_dir, output_path=args.closure, evidence_dir=args.evidence_dir)
        _write(args.result, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        payload = hosted.failure_payload(exc, command_value, phase="CLOSE")
        _write(args.result, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
