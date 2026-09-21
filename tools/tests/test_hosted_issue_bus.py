from __future__ import annotations

import inspect
import json
import unittest
from types import SimpleNamespace

from tools import hosted_issue_bus as bus


class FakeTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        self.calls.append((method.upper(), endpoint))
        if not self.responses:
            raise AssertionError("unexpected transport request")
        return SimpleNamespace(body=json.dumps(self.responses.pop(0)))


class HostedIssueBusTests(unittest.TestCase):
    def test_comment_reader_uses_injected_transport(self):
        transport = FakeTransport([{"id": 23, "body": "ok"}])
        value = bus.get_comment(
            transport,
            repository="EAKerber/MobiliPresenter",
            comment_id=23,
        )
        self.assertEqual(23, value["id"])
        self.assertEqual(
            [("GET", "repos/EAKerber/MobiliPresenter/issues/comments/23")],
            transport.calls,
        )

    def test_comment_pagination_is_bounded_and_provider_backed(self):
        first = [{"id": index + 1} for index in range(100)]
        second = [{"id": 101}]
        transport = FakeTransport([first, second])
        value = bus.list_comments(
            transport,
            repository="EAKerber/MobiliPresenter",
            issue_number=145,
        )
        self.assertEqual(101, len(value))
        self.assertEqual(2, len(transport.calls))
        self.assertTrue(transport.calls[0][1].endswith("per_page=100&page=1"))
        self.assertTrue(transport.calls[1][1].endswith("per_page=100&page=2"))

    def test_issue_discovery_and_comment_submission_are_provider_backed(self):
        transport = FakeTransport([
            [{"number": 145, "title": "MobiliPresenter Remote Canonical Execution Bus"}],
            {"id": 9002},
        ])
        issue_number = bus.find_open_issue(
            transport,
            repository="EAKerber/MobiliPresenter",
            title="MobiliPresenter Remote Canonical Execution Bus",
        )
        comment_id = bus.post_comment(
            transport,
            repository="EAKerber/MobiliPresenter",
            issue_number=issue_number,
            body="request",
        )
        self.assertEqual(145, issue_number)
        self.assertEqual(9002, comment_id)
        self.assertEqual("GET", transport.calls[0][0])
        self.assertEqual("POST", transport.calls[1][0])

    def test_issue_discovery_fails_closed_when_missing_or_ambiguous(self):
        for responses, code in [
            ([[]], "HOSTED_ISSUE_BUS_MISSING"),
            ([[{"number": 1, "title": "bus"}, {"number": 2, "title": "bus"}]], "HOSTED_ISSUE_BUS_AMBIGUOUS"),
        ]:
            with self.subTest(code=code):
                with self.assertRaisesRegex(RuntimeError, code):
                    bus.find_open_issue(
                        FakeTransport(responses),
                        repository="EAKerber/MobiliPresenter",
                        title="bus",
                    )

    def test_missing_provider_blocks_without_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "BLOCKED_EXECUTION_SURFACE"):
            bus.get_comment(
                None,
                repository="EAKerber/MobiliPresenter",
                comment_id=23,
            )
        with self.assertRaisesRegex(RuntimeError, "BLOCKED_EXECUTION_SURFACE"):
            bus.list_comments(
                None,
                repository="EAKerber/MobiliPresenter",
                issue_number=145,
            )

    def test_carrier_helper_does_not_select_provider_or_protocol(self):
        source = inspect.getsource(bus)
        self.assertNotIn("GhApiTransport", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("MOBILIPRESENTER_", source)
        self.assertNotIn("AgentCycle", source)
        self.assertNotIn("Delivery", source)


if __name__ == "__main__":
    unittest.main()
