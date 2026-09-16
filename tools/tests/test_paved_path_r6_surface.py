from __future__ import annotations

import inspect
import unittest

from tools import agent_authoring, agent_delivery, agent_ownership
from tools.agent_tools import journey_entry


class _NoTransport:
    def request(self, *_args, **_kwargs):  # pragma: no cover - must never be called
        raise AssertionError("negative surface canary performed transport I/O")


class PavedPathR6SurfaceTests(unittest.TestCase):
    """Black-box guard for the normal-path cognitive surface.

    This is deliberately not the live R6 traversal proof. It protects the
    precondition for that proof: callers of the paved path must not be forced
    to know hosted transport/protocol identities that the migration exists to
    hide.
    """

    def test_normal_path_functions_hide_hosted_protocol_choreography(self) -> None:
        surfaces = {
            "entry": journey_entry.compose_entry,
            "ownership": agent_ownership.ensure_ownership,
            "authoring": agent_authoring.author_changes,
            "delivery": agent_delivery.compose_delivery,
            "finalization": agent_delivery.project_finalization,
        }
        forbidden = {
            "issue",
            "issue_number",
            "marker",
            "schema",
            "schema_version",
            "command_version",
            "runtime_environment",
            "authority_head",
            "lease_id",
            "binding_hash",
            "comment_id",
            "result_comment_id",
            "cycle_id",
            "context_hash",
        }

        for name, function in surfaces.items():
            with self.subTest(surface=name):
                parameters = set(inspect.signature(function).parameters)
                leaked = sorted(parameters & forbidden)
                self.assertEqual([], leaked)

    def test_entry_negative_canary_is_fail_closed_before_transport(self) -> None:
        value = journey_entry.compose_entry(
            role="manager-gitops",
            declared_intent="continue paved-path refactor",
            work_id="r6-black-box-surface-proof",
            tool_surfaces=["github-connector-tools"],
            inventory_complete=False,
            submit=True,
            transport=_NoTransport(),
        )

        self.assertEqual("UNKNOWN", value["status"])
        self.assertEqual("BUILD_ONLY", value["disposition"])
        self.assertIn("TOOL_SURFACE_INVENTORY_INCOMPLETE", value["blockers"])
        self.assertFalse(value["submitted"])
        self.assertFalse(value["semanticAuthority"])
        self.assertFalse(value["authorizesMutation"])

    def test_paved_surface_does_not_add_an_atomic_finalize_operation(self) -> None:
        self.assertEqual(
            ["COMPLETE_WORK", "RELEASE_OWNERSHIP", "CLOSE_AGENT_CYCLE"],
            agent_delivery.FINALIZATION_ORDER,
        )
        self.assertNotIn("finalize", {
            name
            for module in (journey_entry, agent_ownership, agent_authoring, agent_delivery)
            for name in dir(module)
            if not name.startswith("_")
        })


if __name__ == "__main__":
    unittest.main()
