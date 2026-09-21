from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from tools import hosted_issue_bus


ROOT = Path(__file__).resolve().parents[2]
CLIENTS = [
    "tools/agent_delivery.py",
    "tools/agent_ownership.py",
    "tools/agent_tools/dispatch_host.py",
    "tools/agent_tools/journey_entry.py",
    "tools/agent_tools/trace_collect.py",
    "tools/agent_write_lifecycle.py",
    "tools/agent_write_lifecycle_host.py",
    "tools/hosted_agent_cycle.py",
]


class R8HostedBusIoRetirementTests(unittest.TestCase):
    def test_shared_carrier_remains_provider_and_protocol_neutral(self):
        source = inspect.getsource(hosted_issue_bus)
        for forbidden in (
            "GhApiTransport",
            "subprocess",
            "MOBILIPRESENTER_",
            "AgentCycle",
            "Delivery",
        ):
            self.assertNotIn(forbidden, source)

    def test_migrated_clients_do_not_reimplement_comment_transport(self):
        for relative in CLIENTS:
            source = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                self.assertNotIn("issues/comments/", source)
                self.assertNotIn("comments?per_page=100", source)
                self.assertNotIn('["gh", "api"', source)

    def test_normal_entry_uses_shared_issue_discovery_and_publication(self):
        source = (ROOT / "tools/agent_tools/journey_entry.py").read_text(encoding="utf-8")
        self.assertIn("hosted_issue_bus.find_open_issue", source)
        self.assertIn("hosted_issue_bus.list_comments", source)
        self.assertIn("hosted_issue_bus.post_comment", source)


if __name__ == "__main__":
    unittest.main()
