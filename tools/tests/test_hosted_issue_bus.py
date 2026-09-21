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


def event():
    return {
        "issue": {"number": 145, "title": "MobiliPresenter Remote Canonical Execution Bus"},
        "comment": {"id": 9001, "author_association": "OWNER", "body": "payload"},
        "repository": {"full_name": "EAKerber/MobiliPresenter"},
    }


class HostedIssueBusTests(unittest.TestCase):
    def test_event_envelope_is_transport_only(self):
        value = bus.validate_event_envelope(
            event(),
            repository="EAKerber/MobiliPresenter",
            bus_title="MobiliPresenter Remote Canonical Execution Bus",
        )
        self.assertEqual("payload", value["body"])
        self.assertEqual(
            {"issueNumber": 145, "commentId": 9001},
            bus.event_identity(value),
        )

    def test_event_envelope_fails_closed_on_shared_boundary_errors(self):
        cases = [
            ("pull_request", "PR_FORBIDDEN"),
            ("title", "TITLE_MISMATCH"),
            ("association", "ACTOR_FORBIDDEN"),
            ("repository", "REPOSITORY_MISMATCH"),
            ("body", "BODY_INVALID"),
        ]
        for kind, code in cases:
            value = event()
            if kind == "pull_request":
                value["issue"]["pull_request"] = {"url": "x"}
            elif kind == "title":
                value["issue"]["title"] = "wrong"
            elif kind == "association":
                value["comment"]["author_association"] = "MEMBER"
            elif kind == "repository":
                value["repository"]["full_name"] = "other/repo"
            else:
                value["comment"]["body"] = None
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(RuntimeError, code):
                    bus.validate_event_envelope(
                        value,
                        repository="EAKerber/MobiliPresenter",
                        bus_title="MobiliPresenter Remote Canonical Execution Bus",
                    )

    def test_event_identity_is_separate_from_envelope_validation(self):
        value = event()
        value["comment"]["id"] = 0
        envelope = bus.validate_event_envelope(
            value,
            repository="EAKerber/MobiliPresenter",
            bus_title="MobiliPresenter Remote Canonical Execution Bus",
        )
        with self.assertRaisesRegex(RuntimeError, "IDENTITY_INVALID"):
            bus.event_identity(envelope)

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
