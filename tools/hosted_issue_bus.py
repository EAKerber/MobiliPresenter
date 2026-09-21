from __future__ import annotations

import json
from typing import Any


class HostedIssueBusError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedIssueBusError(code)
    return value


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise HostedIssueBusError(code) from exc


def validate_event_envelope(
    value: Any,
    *,
    repository: str,
    bus_title: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    observed_repository = value.get("repository")
    if (
        not isinstance(issue, dict)
        or not isinstance(comment, dict)
        or not isinstance(observed_repository, dict)
    ):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_EVENT_INVALID")
    if issue.get("pull_request") is not None:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_PR_FORBIDDEN")
    if issue.get("title") != bus_title:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_TITLE_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_ACTOR_FORBIDDEN")
    if observed_repository.get("full_name") != repository:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_REPOSITORY_MISMATCH")
    body = comment.get("body")
    if not isinstance(body, str):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_BODY_INVALID")
    return {
        "issue": issue,
        "comment": comment,
        "repository": observed_repository,
        "body": body,
    }


def event_identity(envelope: dict[str, Any]) -> dict[str, int]:
    if not isinstance(envelope, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_IDENTITY_INVALID")
    issue = envelope.get("issue")
    comment = envelope.get("comment")
    if not isinstance(issue, dict) or not isinstance(comment, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_IDENTITY_INVALID")
    return {
        "issueNumber": _positive_int(
            issue.get("number"), "HOSTED_ISSUE_BUS_IDENTITY_INVALID"
        ),
        "commentId": _positive_int(
            comment.get("id"), "HOSTED_ISSUE_BUS_IDENTITY_INVALID"
        ),
    }


def get_comment(
    transport: Any,
    *,
    repository: str,
    comment_id: int,
) -> dict[str, Any]:
    if transport is None:
        raise HostedIssueBusError("BLOCKED_EXECUTION_SURFACE")
    comment_id = _positive_int(
        comment_id, "HOSTED_ISSUE_BUS_COMMENT_ID_INVALID"
    )
    value = _json_response(
        transport.request(
            "GET",
            f"repos/{repository}/issues/comments/{comment_id}",
        ),
        "HOSTED_ISSUE_BUS_COMMENT_INVALID",
    )
    if not isinstance(value, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENT_INVALID")
    return value


def list_comments(
    transport: Any,
    *,
    repository: str,
    issue_number: int,
) -> list[dict[str, Any]]:
    if transport is None:
        raise HostedIssueBusError("BLOCKED_EXECUTION_SURFACE")
    issue_number = _positive_int(
        issue_number, "HOSTED_ISSUE_BUS_ISSUE_ID_INVALID"
    )
    comments: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{repository}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "HOSTED_ISSUE_BUS_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENTS_INVALID")
        comments.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return comments
    raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENTS_UNBOUNDED")
