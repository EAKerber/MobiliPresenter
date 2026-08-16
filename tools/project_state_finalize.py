#!/usr/bin/env python3
"""One-time M4B finalizer. Deletes itself and all migration-only surfaces."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROJECT_STATE_MODULE = '''"""ProjectState 2.0 current operational contract."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
CURRENT_SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"
CURRENT_SCHEMA_VERSION = "ProjectState 2.0"
REPOSITORY = "EAKerber/MobiliPresenter"
PROJECT_ID = "mobilipresenter"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"STATE_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STATE_JSON_INVALID:{path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"STATE_ROOT_INVALID:{path}")
    return value


def load_state() -> dict[str, Any]:
    return load_json(STATE_PATH)


def _error(errors: list[dict[str, str]], code: str, detail: str) -> None:
    errors.append({"code": code, "detail": detail})


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, unique: bool = False) -> bool:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return False
    return not unique or len(value) == len(set(value))


def validate_current(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(state, dict):
        return [{"code": "STATE_SCHEMA_INVALID", "detail": "state must be an object"}]
    if state.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {CURRENT_SCHEMA_VERSION}"}]
    expected_top = {"schemaVersion", "project", "git", "published", "development"}
    if set(state) != expected_top:
        _error(errors, "STATE_SCHEMA_INVALID", "ProjectState 2.0 top-level fields are invalid")
    for key in ("project", "git", "published", "development"):
        if not isinstance(state.get(key), dict):
            _error(errors, "STATE_SCHEMA_INVALID", f"{key} has invalid type")
    if errors:
        return errors

    project = state["project"]
    if set(project) != {"id", "repository"}:
        _error(errors, "STATE_SCHEMA_INVALID", "project fields are invalid for ProjectState 2.0")
    if project.get("id") != PROJECT_ID:
        _error(errors, "PROJECT_ID_MISMATCH", f"project.id must be {PROJECT_ID}")
    if project.get("repository") != REPOSITORY:
        _error(errors, "REPOSITORY_ID_MISMATCH", f"project.repository must be {REPOSITORY}")

    git_state = state["git"]
    if set(git_state) != {"controlBranch", "activeDevelopmentBranch", "protectedBranches"}:
        _error(errors, "STATE_SCHEMA_INVALID", "git fields are invalid for ProjectState 2.0")
    if not _nonempty_string(git_state.get("controlBranch")):
        _error(errors, "STATE_SCHEMA_INVALID", "git.controlBranch must be a non-empty string")
    active = git_state.get("activeDevelopmentBranch")
    if active is not None and not _nonempty_string(active):
        _error(errors, "STATE_SCHEMA_INVALID", "git.activeDevelopmentBranch must be null or a non-empty string")
    protected = git_state.get("protectedBranches")
    if not _string_list(protected, unique=True) or any(not item for item in protected or []):
        _error(errors, "STATE_SCHEMA_INVALID", "git.protectedBranches must contain unique non-empty strings")

    published = state["published"]
    if set(published) != {"url", "artifactManifest"}:
        _error(errors, "STATE_SCHEMA_INVALID", "published fields are invalid for ProjectState 2.0")
    for key in ("url", "artifactManifest"):
        if not _nonempty_string(published.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"published.{key} must be a non-empty string")

    development = state["development"]
    expected_development = {"initiative", "phase", "checkpoint", "nextTransition", "blockers", "prNumber"}
    if set(development) != expected_development:
        _error(errors, "STATE_SCHEMA_INVALID", "development fields are invalid for ProjectState 2.0")
    for key in ("initiative", "phase", "checkpoint", "nextTransition"):
        if not _nonempty_string(development.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"development.{key} must be a non-empty string")
    if not _string_list(development.get("blockers")):
        _error(errors, "STATE_SCHEMA_INVALID", "development.blockers must be a string list")
    pr_number = development.get("prNumber")
    if pr_number is not None and (not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0):
        _error(errors, "STATE_SCHEMA_INVALID", "development.prNumber must be null or a positive integer")
    if (active is None) != (pr_number is None):
        _error(errors, "DEVELOPMENT_IDENTITY_INCOMPLETE", "activeDevelopmentBranch and prNumber must both be set or both be null")
    return errors


def operational_view(state: dict[str, Any]) -> dict[str, Any]:
    errors = validate_current(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return {
        "project": copy.deepcopy(state["project"]),
        "git": copy.deepcopy(state["git"]),
        "published": copy.deepcopy(state["published"]),
        "development": copy.deepcopy(state["development"]),
    }
'''

TRANSITION_MODULE = '''"""Pure ProjectState checkpoint planner built on Transition Protocol 0.1."""
from __future__ import annotations

import copy
from typing import Any, Callable

from tools import transition_protocol as protocol

Validator = Callable[[dict[str, Any]], list[dict[str, str]]]
PROJECT_STATE_SUBJECT = {"kind": "project-state", "id": "mobilipresenter"}
PROJECT_STATE_AUTHORITY = {"kind": "repository-file", "locator": {"path": "ops/state/project.json"}}


def checkpoint(before: dict[str, Any], checkpoint_name: str, next_transition: str, phase: str | None, *, validator: Validator) -> dict[str, Any]:
    errors = validator(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    if not isinstance(checkpoint_name, str) or not checkpoint_name.strip():
        raise RuntimeError("CHECKPOINT_NAME_INVALID")
    if not isinstance(next_transition, str) or not next_transition.strip():
        raise RuntimeError("CHECKPOINT_NEXT_TRANSITION_INVALID")
    if phase is not None and (not isinstance(phase, str) or not phase.strip()):
        raise RuntimeError("CHECKPOINT_PHASE_INVALID")
    candidate = copy.deepcopy(before)
    candidate["development"]["checkpoint"] = checkpoint_name.strip()
    candidate["development"]["nextTransition"] = next_transition.strip()
    if phase is not None:
        candidate["development"]["phase"] = phase.strip()
    candidate_errors = validator(candidate)
    if candidate_errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{candidate_errors[0]['detail']}")
    intent = {"checkpoint": checkpoint_name.strip(), "nextTransition": next_transition.strip(), "phase": phase.strip() if phase is not None else None}
    return protocol.build_plan(domain="project-state", action="checkpoint", subject=PROJECT_STATE_SUBJECT, authority=PROJECT_STATE_AUTHORITY, before=before, candidate=candidate, intent=intent, reversibility="revertible")


def validate_checkpoint_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state" or plan["action"] != "checkpoint":
        raise RuntimeError("CHECKPOINT_PLAN_DOMAIN_INVALID")
    if plan["subject"] != PROJECT_STATE_SUBJECT:
        raise RuntimeError("CHECKPOINT_PLAN_SUBJECT_INVALID")
    if plan["authority"] != PROJECT_STATE_AUTHORITY:
        raise RuntimeError("CHECKPOINT_PLAN_AUTHORITY_INVALID")
    intent = plan["intent"]
    if set(intent) != {"checkpoint", "nextTransition", "phase"}:
        raise RuntimeError("CHECKPOINT_PLAN_INTENT_INVALID")
    errors = validator(plan["candidate"])
    if errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{errors[0]['detail']}")
    development = plan["candidate"]["development"]
    if development["checkpoint"] != intent["checkpoint"] or development["nextTransition"] != intent["nextTransition"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    if intent["phase"] is not None and development["phase"] != intent["phase"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan
'''

APPLY_MODULE = '''"""Fail-closed ProjectState checkpoint executor for Transition Protocol 0.1 plans."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from tools import project_state_transition as transition
from tools import transition_protocol as protocol

Loader = Callable[[], dict[str, Any]]
Validator = Callable[[dict[str, Any]], list[dict[str, str]]]
GitObserver = Callable[[], dict[str, Any]]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _restore_bytes(path: Path, previous_bytes: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(previous_bytes)
        restore_tmp = Path(handle.name)
    try:
        os.replace(restore_tmp, path)
    finally:
        if restore_tmp.exists():
            restore_tmp.unlink()


def apply(plan: dict[str, Any], expected_plan: str | None, *, state_path: Path, load_state: Loader, validator: Validator, observe_git: GitObserver) -> dict[str, Any]:
    transition.validate_checkpoint_plan(plan, validator=validator)
    protocol.require_expected_plan(plan, expected_plan)
    current = load_state()
    errors = validator(current)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    protocol.verify_before_state(plan, current)
    active = current["git"].get("activeDevelopmentBranch")
    if active is None:
        raise RuntimeError("CHECKPOINT_NO_ACTIVE_DEVELOPMENT")
    git = observe_git()
    if not git.get("worktree"):
        raise RuntimeError("CHECKPOINT_NOT_A_WORKTREE")
    if git.get("branch") != active:
        raise RuntimeError(f"CHECKPOINT_WRONG_BRANCH:{git.get('branch')}")
    if git.get("dirty"):
        raise RuntimeError("CHECKPOINT_DIRTY_WORKTREE")
    previous_bytes = state_path.read_bytes()
    wrote = False
    try:
        _atomic_write(state_path, plan["candidate"])
        wrote = True
        readback = load_state()
        errors = validator(readback)
        if errors:
            raise RuntimeError(f"STATE_READBACK_INVALID:{errors[0]['detail']}")
        receipt = protocol.build_receipt(plan, readback)
        protocol.validate_receipt(receipt, plan)
        return receipt
    except Exception:
        if wrote:
            _restore_bytes(state_path, previous_bytes)
            restored = load_state()
            if protocol.state_hash(restored) != plan["beforeStateHash"]:
                raise RuntimeError("PROJECT_STATE_ROLLBACK_FAILED")
        raise
'''

TEST_PROJECT_STATE = '''import copy
import unittest

from tools import project_state


class ProjectStateTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": None, "protectedBranches": ["coordination/leases"]},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "Viewer Next", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "blockers": [], "prNumber": None},
        }

    def test_v2_is_the_only_current_contract(self):
        value = self.state()
        self.assertEqual(project_state.validate_current(value), [])
        self.assertEqual(project_state.operational_view(value), value | {"schemaVersion": value["schemaVersion"]} if False else {k: copy.deepcopy(value[k]) for k in ("project", "git", "published", "development")})
        old = copy.deepcopy(value)
        old["schemaVersion"] = "ProjectState 1.0"
        self.assertTrue(any(item["code"] == "STATE_SCHEMA_UNSUPPORTED" for item in project_state.validate_current(old)))

    def test_removed_baggage_is_rejected(self):
        cases = [
            ("top", "operations", {}),
            ("project", "productInvariants", {}),
            ("git", "publishedBranch", "main"),
            ("git", "preserveBranches", []),
            ("published", "release", "x"),
            ("published", "artifactSha256", "a" * 64),
            ("development", "constraints", []),
            ("development", "plan", "x"),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                state = self.state()
                if section == "top":
                    state[key] = value
                else:
                    state[section][key] = value
                self.assertTrue(project_state.validate_current(state))

    def test_development_identity_remains_atomic(self):
        state = self.state()
        state["development"]["prNumber"] = 7
        self.assertTrue(any(item["code"] == "DEVELOPMENT_IDENTITY_INCOMPLETE" for item in project_state.validate_current(state)))


if __name__ == "__main__":
    unittest.main()
'''

TEST_MIGRATION_EVIDENCE = '''import json
import unittest
from pathlib import Path

from tools import project_state
from tools import transition_protocol as protocol

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops" / "evidence" / "project-state" / "project-state-2.0-migration.json"


class ProjectStateMigrationEvidenceTests(unittest.TestCase):
    def test_verified_migration_evidence_matches_current_authority(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        state = project_state.load_state()
        self.assertEqual(evidence["schemaVersion"], "ProjectStateMigrationEvidence 0.1")
        self.assertEqual(evidence["fromSchemaVersion"], "ProjectState 1.0")
        self.assertEqual(evidence["toSchemaVersion"], "ProjectState 2.0")
        self.assertEqual(evidence["migrationMap"]["constraintCount"], 32)
        self.assertEqual(evidence["migrationMap"]["unresolvedCount"], 0)
        self.assertTrue(evidence["publicationParity"]["all"])
        self.assertTrue(evidence["protectedBranchesParity"])
        plan = evidence["transitionPlan"]
        receipt = evidence["transitionReceipt"]
        protocol.validate_plan(plan)
        protocol.validate_receipt(receipt, plan)
        self.assertTrue(receipt["verified"])
        self.assertEqual(protocol.state_hash(state), plan["afterStateHash"])
        self.assertEqual(receipt["readbackStateHash"], plan["afterStateHash"])
        self.assertEqual(project_state.validate_current(state), [])


if __name__ == "__main__":
    unittest.main()
'''

TEST_BOUNDARIES = '''import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSUMERS = [
    "tools/agent.py",
    "tools/project_sensors.py",
    "tools/project_machine.py",
    "tools/project_coherence.py",
    "tools/prune_plan.py",
    "tools/maintenance_inspect.py",
]
FORBIDDEN = [
    '"productInvariants"',
    '"publishedBranch"',
    '"preserveBranches"',
    '"artifactSha256"',
    '"constraints"',
    '"toolboxPhase"',
    '"canonicalState"',
    '["plan"]',
]


class ProjectStateConsumerBoundaryTests(unittest.TestCase):
    def test_migrated_consumers_do_not_read_removed_fields(self):
        violations = []
        for relative in CONSUMERS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for token in FORBIDDEN:
                if token in text:
                    violations.append(f"{relative}:{token}")
        self.assertEqual(violations, [])

    def test_live_authority_and_canonical_schema_are_v2_only(self):
        state = (ROOT / "ops/state/project.json").read_text(encoding="utf-8")
        schema = (ROOT / "ops/schemas/project-state.schema.json").read_text(encoding="utf-8")
        self.assertIn('"schemaVersion": "ProjectState 2.0"', state)
        self.assertIn('"ProjectState 2.0"', schema)
        self.assertNotIn('"schemaVersion": "ProjectState 1.0"', state)
        self.assertFalse((ROOT / "ops/schemas/project-state-2.0.schema.json").exists())
        self.assertFalse((ROOT / "ops/migrations/project-state-2.0.json").exists())

    def test_runtime_compatibility_helpers_are_retired(self):
        text = (ROOT / "tools/project_state.py").read_text(encoding="utf-8")
        for token in ("validate_v1", "validate_v2", "validate_compatible", "migrate_v1_to_v2", "MIGRATION_MAP_PATH", "CANDIDATE_V2_SCHEMA_PATH"):
            self.assertNotIn(token, text)
        self.assertNotIn("validate_state_shape", (ROOT / "tools/agent.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
'''

TEST_TRANSITION = '''import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import project_state
from tools import project_state_apply
from tools import project_state_transition
from tools import transition_protocol as protocol


class ProjectStateTransitionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": "work/operations/test-transition", "protectedBranches": []},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "Test", "phase": "active", "checkpoint": "BEFORE", "nextTransition": "next-before", "blockers": [], "prNumber": 1},
        }

    def plan(self):
        return project_state_transition.checkpoint(self.state(), "AFTER", "next-after", None, validator=project_state.validate_current)

    def test_checkpoint_plan_is_deterministic(self):
        first = self.plan(); second = self.plan()
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], "TransitionPlan 0.1")
        self.assertEqual(first["candidate"]["development"]["checkpoint"], "AFTER")

    def test_checkpoint_plan_validation_binds_candidate_to_intent(self):
        plan = self.plan(); plan["candidate"]["development"]["checkpoint"] = "OTHER"
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: value for key, value in plan.items() if key != "planHash"}; plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH"):
            project_state_transition.validate_checkpoint_plan(plan, validator=project_state.validate_current)

    def test_apply_guards_and_verified_receipt(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"; path.write_text(json.dumps(self.state()) + "\\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
                project_state_apply.apply(plan, None, state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            receipt = project_state_apply.apply(plan, plan["planHash"], state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            self.assertTrue(receipt["verified"]); protocol.validate_receipt(receipt, plan)

    def test_post_write_failure_restores_previous_state(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"; original = json.dumps(self.state()) + "\\n"; path.write_text(original, encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            with mock.patch("tools.project_state_apply.protocol.build_receipt", side_effect=RuntimeError("TEST_POST_WRITE_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "TEST_POST_WRITE_FAILURE"):
                    project_state_apply.apply(plan, plan["planHash"], state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
'''

PROJECT_STATE_CONTRACT_FN = '''\ndef check_project_state_contract()->list[str]:
    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("project-state")
    if not isinstance(contract,dict):return ["SEMANTIC_PROJECT_STATE_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.project_state.validate_current":errors.append("SEMANTIC_PROJECT_STATE_VALIDATOR_MISMATCH")
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}
    expected={"schemaVersion","project","git","published","development"}
    if set(properties)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_FIELDS_MISMATCH")
    if set(schema.get("required") or [])!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REQUIRED_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=project_state.CURRENT_SCHEMA_VERSION:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_VERSION_MISMATCH")
    state=project_state.load_state();runtime_errors=project_state.validate_current(state)
    if runtime_errors:errors.append(f"SEMANTIC_PROJECT_STATE_RUNTIME_INVALID:{runtime_errors[0]['code']}")
    if set(state)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REJECTS_RUNTIME")
    nested={"project":{"id","repository"},"git":{"controlBranch","activeDevelopmentBranch","protectedBranches"},"published":{"url","artifactManifest"},"development":{"initiative","phase","checkpoint","nextTransition","blockers","prNumber"}}
    for name,fields in nested.items():
        spec=properties.get(name) if isinstance(properties.get(name),dict) else {};required=set(spec.get("required") or []);value=state.get(name)
        if required!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_REQUIRED_MISMATCH")
        if not isinstance(value,dict) or set(value)!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_RUNTIME_FIELDS_MISMATCH")
    return errors
'''


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    state = json.loads(read("ops/state/project.json"))
    evidence = json.loads(read("ops/evidence/project-state/project-state-2.0-migration.json"))
    if state.get("schemaVersion") != "ProjectState 2.0":
        raise RuntimeError("FINALIZE_STATE_NOT_V2")
    receipt = evidence.get("transitionReceipt") if isinstance(evidence, dict) else None
    if not isinstance(receipt, dict) or receipt.get("verified") is not True or receipt.get("readbackStateHash") != receipt.get("afterStateHash"):
        raise RuntimeError("FINALIZE_MIGRATION_EVIDENCE_INVALID")

    candidate_schema = json.loads(read("ops/schemas/project-state-2.0.schema.json"))
    candidate_schema["title"] = "MobiliPresenter ProjectState 2.0"
    write("ops/schemas/project-state.schema.json", json.dumps(candidate_schema, indent=2, ensure_ascii=False))

    write("tools/project_state.py", PROJECT_STATE_MODULE)
    write("tools/project_state_transition.py", TRANSITION_MODULE)
    write("tools/project_state_apply.py", APPLY_MODULE)

    agent_path = ROOT / "tools/agent.py"
    agent = agent_path.read_text(encoding="utf-8")
    alias = '''\n# Temporary compatibility alias for callers/tests. Internal consumers use tools.project_state directly.\ndef validate_state_shape(state: dict[str, Any]) -> list[dict[str, str]]:\n    return project_state.validate_current(state)\n'''
    if alias not in agent:
        raise RuntimeError("FINALIZE_AGENT_ALIAS_NOT_FOUND")
    agent_path.write_text(agent.replace(alias, "\n"), encoding="utf-8")

    registry_path = ROOT / "ops/semantics/registry.json"
    registry = registry_path.read_text(encoding="utf-8")
    needle = '    "operational-semantics": {"owner": "operations-core", "semanticValidator": "tools.semantics.registry.validate_registry", "structuralSchema": "ops/schemas/operational-semantics.schema.json"},\n    "source-build":'
    replacement = '    "operational-semantics": {"owner": "operations-core", "semanticValidator": "tools.semantics.registry.validate_registry", "structuralSchema": "ops/schemas/operational-semantics.schema.json"},\n    "project-state": {"owner": "operations-core", "semanticValidator": "tools.project_state.validate_current", "structuralSchema": "ops/schemas/project-state.schema.json"},\n    "source-build":'
    if needle not in registry:
        raise RuntimeError("FINALIZE_REGISTRY_CONTRACT_INSERTION_POINT_NOT_FOUND")
    registry_path.write_text(registry.replace(needle, replacement), encoding="utf-8")

    contracts_path = ROOT / "tools/semantics/contracts.py"
    contracts = contracts_path.read_text(encoding="utf-8")
    marker = 'def check_contracts()->list[str]:\n'
    if marker not in contracts or "def check_project_state_contract" in contracts:
        raise RuntimeError("FINALIZE_SEMANTIC_CONTRACT_INSERTION_INVALID")
    contracts = contracts.replace(marker, PROJECT_STATE_CONTRACT_FN + marker)
    old = '    errors=check_capability_gates_contract();errors.extend(check_operational_semantics_contract());errors.extend(check_source_build_contract());return errors\n'
    new = '    errors=check_capability_gates_contract();errors.extend(check_operational_semantics_contract());errors.extend(check_source_build_contract());errors.extend(check_project_state_contract());return errors\n'
    if old not in contracts:
        raise RuntimeError("FINALIZE_SEMANTIC_CONTRACT_AGGREGATE_NOT_FOUND")
    contracts_path.write_text(contracts.replace(old, new), encoding="utf-8")

    semantic_tests_path = ROOT / "tools/tests/test_semantic_contracts.py"
    semantic_tests = semantic_tests_path.read_text(encoding="utf-8")
    semantic_tests = semantic_tests.replace('from tools.semantics.contracts import check_capability_gates_contract\n', 'from tools.semantics.contracts import check_capability_gates_contract, check_project_state_contract\n')
    insert = '''\n    def test_project_state_contract_is_conformant(self):\n        self.assertEqual([], check_project_state_contract())\n'''
    if "test_project_state_contract_is_conformant" not in semantic_tests:
        semantic_tests = semantic_tests.replace('\n\nif __name__ == "__main__":', insert + '\n\nif __name__ == "__main__":')
    semantic_tests_path.write_text(semantic_tests, encoding="utf-8")

    write("tools/tests/test_project_state.py", TEST_PROJECT_STATE)
    write("tools/tests/test_project_state_migration.py", TEST_MIGRATION_EVIDENCE)
    write("tools/tests/test_project_state_consumer_boundaries.py", TEST_BOUNDARIES)
    write("tools/tests/test_project_state_transition.py", TEST_TRANSITION)

    adr_path = ROOT / "docs/adr/0006-project-state-2.0.md"
    adr = adr_path.read_text(encoding="utf-8")
    adr = adr.replace('- Status: proposed for authority migration in M4B; consumer preparation implemented in M4A', '- Status: accepted; ProjectState 2.0 integrated in M4B')
    adr = adr.replace('M4B must remove temporary V1 compatibility and leave the canonical ProjectState schema accepting ProjectState 2.0 only.', 'M4B completed the authority migration with a verified TransitionReceipt, removed temporary V1 runtime compatibility, and left the canonical ProjectState schema accepting ProjectState 2.0 only. The migration map remains recoverable at source control revision `031ce02039030078fdca3b40b282f1f789edca09`.')
    adr_path.write_text(adr, encoding="utf-8")

    agents_path = ROOT / "AGENTS.md"
    agents = agents_path.read_text(encoding="utf-8")
    agents = agents.replace('git.preserveBranches', 'git.protectedBranches')
    agents = agents.replace('- estado operacional corrente: `ops/state/project.json`;', '- estado operacional corrente (somente fatos mutáveis/correntes; contratos, tooling discovery e metadata derivável não pertencem ao state): `ops/state/project.json`;')
    agents_path.write_text(agents, encoding="utf-8")

    for relative in (
        "ops/schemas/project-state-2.0.schema.json",
        "ops/migrations/project-state-2.0.json",
        "ops/migrations/project-state-2.0.plan.json",
        "ops/migrations/project-state-2.0.finalize-request.json",
        "tools/project_state_migrate_live.py",
        "tools/project_state_finalize.py",
        "tools/tests/test_project_state_schema_migration.py",
        ".github/workflows/project-state-migration.yml",
    ):
        (ROOT / relative).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
