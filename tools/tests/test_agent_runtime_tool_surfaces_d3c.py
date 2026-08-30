import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import agent
from tools import runtime_capabilities


SURFACE = "github-connector-tools"


def provider_payload(**providers):
    return {
        "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
        "providers": providers,
    }


class AgentRuntimeToolSurfacesD3CTests(unittest.TestCase):
    def test_complete_surface_derives_connector_capabilities_without_temp_bundle(self):
        with mock.patch.object(
            agent.runtime_capabilities,
            "local_provider_observations",
            return_value=provider_payload(),
        ):
            base = agent._runtime_surface_base(
                ["agent", "begin"],
                [SURFACE],
                inventory_complete=True,
            )
        inspection = runtime_capabilities.build_inspection(base)
        self.assertEqual(base["providers"]["github-connector"]["status"], "PASS")
        self.assertEqual(
            inspection["capabilities"]["github.git-data.write"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["github.expected-head-write"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["github.mutation-readback"]["status"], "PASS"
        )

    def test_incomplete_surface_inventory_preserves_unknown(self):
        with mock.patch.object(
            agent.runtime_capabilities,
            "local_provider_observations",
            return_value=provider_payload(),
        ):
            base = agent._runtime_surface_base(
                ["agent", "begin"],
                [SURFACE],
                inventory_complete=False,
            )
        inspection = runtime_capabilities.build_inspection(base)
        self.assertEqual(base["providers"]["github-connector"]["status"], "UNKNOWN")
        self.assertEqual(
            inspection["capabilities"]["github.git-data.write"]["status"], "UNKNOWN"
        )

    def test_surface_and_explicit_bundle_cannot_write_same_provider(self):
        explicit = provider_payload(
            **{
                "github-connector": {
                    "status": "PASS",
                    "features": ["repository-read"],
                    "reason": None,
                }
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(json.dumps(explicit), encoding="utf-8")
            with mock.patch.object(
                agent.runtime_capabilities,
                "local_provider_observations",
                return_value=provider_payload(),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "RUNTIME_PROVIDER_OBSERVATION_SOURCE_CONFLICT:github-connector",
                ):
                    agent._runtime_surface_base(
                        ["agent", "begin", "--runtime-providers", str(path)],
                        [SURFACE],
                        inventory_complete=True,
                    )

    def test_surface_flags_are_facade_only_and_delegate_cleanly(self):
        original_argv = list(sys.argv)
        observed = {}

        def fake_main():
            observed["argv"] = list(sys.argv)
            observed["providers"] = runtime_capabilities.local_provider_observations()
            return 17

        try:
            sys.argv = [
                "agent",
                "begin",
                "--runtime-tool-surface",
                SURFACE,
                "--runtime-tool-surfaces-complete",
            ]
            with mock.patch.object(
                agent.runtime_capabilities,
                "local_provider_observations",
                return_value=provider_payload(),
            ), mock.patch.object(agent._commands, "main", side_effect=fake_main):
                result = agent.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(result, 17)
        self.assertEqual(observed["argv"], ["agent", "begin"])
        self.assertEqual(
            observed["providers"]["providers"]["github-connector"]["status"],
            "PASS",
        )

    def test_no_surface_flags_preserve_existing_delegate(self):
        argv = ["agent", "begin", "--runtime-providers", "providers.json"]
        clean, surfaces, complete, observed = agent._extract_runtime_tool_surfaces(argv)
        self.assertEqual(clean, argv)
        self.assertEqual(surfaces, [])
        self.assertFalse(complete)
        self.assertFalse(observed)

    def test_surface_flags_fail_closed_outside_begin_or_doctor(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "RUNTIME_TOOL_SURFACES_REQUIRE_BEGIN_OR_DOCTOR",
        ):
            agent._runtime_surface_base(
                ["agent", "status"],
                [SURFACE],
                inventory_complete=True,
            )


if __name__ == "__main__":
    unittest.main()
