from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from tools import agent_cycle_identity

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "ops" / "schemas" / "agent-cycle-handle.schema.json"


def _structural_accepts(value: object) -> bool:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        return False
    required = set(schema["required"])
    if set(value) != required or schema.get("additionalProperties") is not False:
        return False
    props = schema["properties"]
    if value.get("schemaVersion") != props["schemaVersion"]["const"]:
        return False
    for key in ("repository", "resumeToken"):
        item = value.get(key)
        if not isinstance(item, str) or len(item) < props[key]["minLength"]:
            return False
    for key in ("cycleId", "cycleInstanceId", "handleHash"):
        item = value.get(key)
        if not isinstance(item, str) or re.fullmatch(props[key]["pattern"], item) is None:
            return False
    for key in ("readOnly", "semanticAuthority", "authorizesMutation"):
        if value.get(key) is not props[key]["const"]:
            return False
    context = value.get("context")
    context_schema = props["context"]
    if not isinstance(context, dict) or set(context) != set(context_schema["required"]):
        return False
    if context_schema.get("additionalProperties") is not False:
        return False
    if not isinstance(context.get("schemaVersion"), str) or not context["schemaVersion"]:
        return False
    if not isinstance(context.get("contextHash"), str) or re.fullmatch(
        context_schema["properties"]["contextHash"]["pattern"], context["contextHash"]
    ) is None:
        return False
    actor = value.get("actor")
    actor_schema = props["actor"]
    if not isinstance(actor, dict) or set(actor) != set(actor_schema["required"]):
        return False
    if actor_schema.get("additionalProperties") is not False:
        return False
    for key in actor_schema["required"]:
        if not isinstance(actor.get(key), str) or not actor[key]:
            return False
    return True


def _valid_handle() -> dict[str, object]:
    return agent_cycle_identity.build_handle(
        repository="EAKerber/MobiliPresenter",
        cycle_id="cycle-" + "a" * 20,
        cycle_instance_id="cycle-instance-" + "b" * 24,
        context_schema_version="AgentCycleContext 0.3",
        context_hash="c" * 64,
        actor={
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-1",
        },
        resume_token="opaque-provider-token",
    )


class AgentCycleHandlePublicR2B1Tests(unittest.TestCase):
    def _semantic_accepts(self, value: object) -> bool:
        try:
            agent_cycle_identity.validate_handle(value)
        except RuntimeError:
            return False
        return True

    def assertStructuralParity(self, value: object, expected: bool) -> None:
        self.assertEqual(expected, _structural_accepts(value))
        self.assertEqual(expected, self._semantic_accepts(value))

    def test_positive_contract_parity(self):
        value = _valid_handle()
        self.assertStructuralParity(value, True)

    def test_negative_structural_contract_parity(self):
        base = _valid_handle()
        cases: list[object] = []

        extra = copy.deepcopy(base)
        extra["extra"] = True
        cases.append(extra)

        missing = copy.deepcopy(base)
        missing.pop("resumeToken")
        cases.append(missing)

        bad_cycle = copy.deepcopy(base)
        bad_cycle["cycleId"] = "cycle-NOT-CANONICAL"
        cases.append(bad_cycle)

        bad_instance = copy.deepcopy(base)
        bad_instance["cycleInstanceId"] = "cycle-instance-short"
        cases.append(bad_instance)

        bad_context = copy.deepcopy(base)
        bad_context["context"]["contextHash"] = "x" * 63
        cases.append(bad_context)

        bad_actor = copy.deepcopy(base)
        bad_actor["actor"]["extra"] = "x"
        cases.append(bad_actor)

        empty_token = copy.deepcopy(base)
        empty_token["resumeToken"] = ""
        cases.append(empty_token)

        authority = copy.deepcopy(base)
        authority["authorizesMutation"] = True
        cases.append(authority)

        for value in cases:
            with self.subTest(value=value):
                self.assertStructuralParity(value, False)

    def test_hash_binding_is_semantic_not_a_second_schema_definition(self):
        tampered = copy.deepcopy(_valid_handle())
        tampered["actor"]["sessionId"] = "session-2"
        self.assertTrue(_structural_accepts(tampered))
        self.assertFalse(self._semantic_accepts(tampered))

    def test_schema_matches_current_python_field_sets(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(agent_cycle_identity.HANDLE_SCHEMA, schema["title"])
        self.assertEqual(agent_cycle_identity.HANDLE_FIELDS, set(schema["required"]))
        self.assertEqual(agent_cycle_identity.HANDLE_FIELDS, set(schema["properties"]))
        self.assertEqual(agent_cycle_identity.CONTEXT_FIELDS, set(schema["properties"]["context"]["required"]))
        self.assertEqual(agent_cycle_identity.ACTOR_FIELDS, set(schema["properties"]["actor"]["required"]))
        self.assertEqual({"type", "minLength"}, set(schema["properties"]["resumeToken"]))


if __name__ == "__main__":
    unittest.main()
