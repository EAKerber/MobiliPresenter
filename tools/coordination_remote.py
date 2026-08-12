from __future__ import annotations

import base64
import copy
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Protocol
from urllib.parse import quote

from tools import coordination

DEFAULT_REPOSITORY = "EAKerber/MobiliPresenter"
DEFAULT_AUTHORITY_BRANCH = "coordination/leases"
DEFAULT_STATE_PATH = "ops/coordination/leases.json"


class CoordinationRemoteError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


class ApiError(RuntimeError):
    def __init__(self, status: int | None, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP_{status}:{detail}" if status is not None else detail)


@dataclass(frozen=True)
class ApiResponse:
    status: int | None
    headers: dict[str, str]
    body: str


@dataclass(frozen=True)
class AuthorityObservation:
    head_sha: str
    tree_sha: str
    state: dict[str, Any]
    authority_now: datetime


@dataclass(frozen=True)
class AppliedTransition:
    before_sha: str
    after_sha: str
    authority_now: datetime
    state: dict[str, Any]
    event: dict[str, Any]


class Transport(Protocol):
    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        include_headers: bool = False,
    ) -> ApiResponse: ...


class GhApiTransport:
    """Minimal GitHub REST transport backed by authenticated `gh api`.

    This transport intentionally exposes only the primitive needed by the
    coordination authority adapter. It never falls back to local time or a
    local coordination file when remote observation fails.
    """

    def __init__(self, gh_executable: str = "gh") -> None:
        self.gh_executable = gh_executable

    @staticmethod
    def _parse_included(output: str) -> ApiResponse:
        normalized = output.replace("\r\n", "\n")
        if "\n\n" not in normalized:
            return ApiResponse(status=None, headers={}, body=normalized)
        header_text, body = normalized.split("\n\n", 1)
        lines = header_text.splitlines()
        status: int | None = None
        headers: dict[str, str] = {}
        if lines:
            match = re.match(r"HTTP/\S+\s+(\d{3})", lines[0].strip())
            if match:
                status = int(match.group(1))
        for line in lines[1:]:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
        return ApiResponse(status=status, headers=headers, body=body)

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        include_headers: bool = False,
    ) -> ApiResponse:
        if shutil.which(self.gh_executable) is None:
            raise CoordinationRemoteError("COORDINATION_REMOTE_UNAVAILABLE", "gh executable not found")
        command = [self.gh_executable, "api", "--method", method.upper()]
        if include_headers:
            command.append("--include")
        if payload is not None:
            command.extend(["--input", "-"])
        command.append(endpoint)
        proc = subprocess.run(
            command,
            input=json.dumps(payload, separators=(",", ":")) if payload is not None else None,
            text=True,
            capture_output=True,
            check=False,
        )
        response = self._parse_included(proc.stdout) if include_headers else ApiResponse(None, {}, proc.stdout)
        if proc.returncode != 0:
            detail = (proc.stderr or response.body or proc.stdout).strip()
            status = response.status
            if status is None:
                match = re.search(r"\b([45]\d\d)\b", detail)
                status = int(match.group(1)) if match else None
            raise ApiError(status, detail)
        return response


def _json_body(response: ApiResponse, *, operation: str) -> dict[str, Any]:
    try:
        value = json.loads(response.body)
    except json.JSONDecodeError as exc:
        raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_RESPONSE", operation) from exc
    if not isinstance(value, dict):
        raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_RESPONSE", f"{operation} did not return object")
    return value


def _server_time(headers: dict[str, str]) -> datetime:
    value = headers.get("date")
    if not value:
        raise CoordinationRemoteError("COORDINATION_TIME_UNAVAILABLE", "GitHub Date header missing")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise CoordinationRemoteError("COORDINATION_TIME_UNAVAILABLE", "GitHub Date header invalid") from exc
    if parsed.tzinfo is None:
        raise CoordinationRemoteError("COORDINATION_TIME_UNAVAILABLE", "GitHub Date header lacks timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_RESPONSE", f"{label} missing or invalid")
    return value


class GitHubCoordinationAuthority:
    def __init__(
        self,
        transport: Transport,
        *,
        repository: str = DEFAULT_REPOSITORY,
        authority_branch: str = DEFAULT_AUTHORITY_BRANCH,
        state_path: str = DEFAULT_STATE_PATH,
    ) -> None:
        self.transport = transport
        self.repository = repository
        self.authority_branch = authority_branch
        self.state_path = state_path

    @property
    def _ref_endpoint(self) -> str:
        encoded = quote(self.authority_branch, safe="")
        return f"repos/{self.repository}/git/ref/heads/{encoded}"

    @property
    def _update_ref_endpoint(self) -> str:
        encoded = quote(self.authority_branch, safe="")
        return f"repos/{self.repository}/git/refs/heads/{encoded}"

    def _state_endpoint(self, ref: str) -> str:
        encoded_path = quote(self.state_path, safe="/")
        encoded_ref = quote(ref, safe="")
        return f"repos/{self.repository}/contents/{encoded_path}?ref={encoded_ref}"

    def observe(self) -> AuthorityObservation:
        try:
            ref_response = self.transport.request("GET", self._ref_endpoint, include_headers=True)
            ref_payload = _json_body(ref_response, operation="read authority ref")
            authority_now = _server_time(ref_response.headers)
            head_sha = _require_sha(ref_payload.get("object", {}).get("sha") if isinstance(ref_payload.get("object"), dict) else None, "authority head")

            commit_response = self.transport.request("GET", f"repos/{self.repository}/git/commits/{head_sha}")
            commit_payload = _json_body(commit_response, operation="read authority commit")
            tree_sha = _require_sha(commit_payload.get("tree", {}).get("sha") if isinstance(commit_payload.get("tree"), dict) else None, "authority tree")

            state_response = self.transport.request("GET", self._state_endpoint(head_sha))
            state_payload = _json_body(state_response, operation="read coordination state")
            encoded = state_payload.get("content")
            encoding = state_payload.get("encoding")
            if not isinstance(encoded, str) or encoding != "base64":
                raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_RESPONSE", "coordination state content is not base64")
            try:
                decoded = base64.b64decode(encoded, validate=False).decode("utf-8")
                state = json.loads(decoded)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_STATE", "cannot decode coordination state") from exc
            if not isinstance(state, dict):
                raise CoordinationRemoteError("COORDINATION_REMOTE_INVALID_STATE", "coordination state root is not object")
            coordination.validate_state(state)
            return AuthorityObservation(head_sha=head_sha, tree_sha=tree_sha, state=state, authority_now=authority_now)
        except CoordinationRemoteError:
            raise
        except ApiError as exc:
            raise CoordinationRemoteError("COORDINATION_REMOTE_UNAVAILABLE", exc.detail) from exc

    def _create_blob(self, content: str) -> str:
        response = self.transport.request(
            "POST",
            f"repos/{self.repository}/git/blobs",
            payload={"content": content, "encoding": "utf-8"},
        )
        return _require_sha(_json_body(response, operation="create authority blob").get("sha"), "blob sha")

    def _create_tree(self, base_tree_sha: str, blob_sha: str) -> str:
        response = self.transport.request(
            "POST",
            f"repos/{self.repository}/git/trees",
            payload={
                "base_tree": base_tree_sha,
                "tree": [{"path": self.state_path, "mode": "100644", "type": "blob", "sha": blob_sha}],
            },
        )
        return _require_sha(_json_body(response, operation="create authority tree").get("sha"), "tree sha")

    def _create_commit(self, parent_sha: str, tree_sha: str, message: str) -> str:
        response = self.transport.request(
            "POST",
            f"repos/{self.repository}/git/commits",
            payload={"message": message, "tree": tree_sha, "parents": [parent_sha]},
        )
        return _require_sha(_json_body(response, operation="create authority commit").get("sha"), "commit sha")

    def _advance_ref(self, commit_sha: str) -> None:
        try:
            self.transport.request(
                "PATCH",
                self._update_ref_endpoint,
                payload={"sha": commit_sha, "force": False},
            )
        except ApiError as exc:
            lowered = exc.detail.lower()
            if exc.status == 422 and ("fast forward" in lowered or "fast-forward" in lowered):
                raise CoordinationRemoteError("COORDINATION_REF_DRIFT", "authority advanced after observation") from exc
            raise CoordinationRemoteError("COORDINATION_REMOTE_WRITE_FAILED", exc.detail) from exc

    def mutate(
        self,
        planner: Callable[[dict[str, Any], datetime], tuple[dict[str, Any], dict[str, Any]]],
        *,
        message: str,
    ) -> AppliedTransition:
        if not isinstance(message, str) or not message.strip():
            raise CoordinationRemoteError("COORDINATION_MESSAGE_INVALID", "commit message is required")
        observed = self.observe()
        candidate, event = planner(copy.deepcopy(observed.state), observed.authority_now)
        if not isinstance(candidate, dict) or not isinstance(event, dict):
            raise CoordinationRemoteError("COORDINATION_PLANNER_INVALID", "planner must return state and event objects")

        candidate = copy.deepcopy(candidate)
        candidate["revision"] = observed.head_sha
        coordination.validate_state(candidate)
        encoded = json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"

        try:
            blob_sha = self._create_blob(encoded)
            tree_sha = self._create_tree(observed.tree_sha, blob_sha)
            commit_sha = self._create_commit(observed.head_sha, tree_sha, message.strip())
            self._advance_ref(commit_sha)
        except CoordinationRemoteError:
            raise
        except ApiError as exc:
            raise CoordinationRemoteError("COORDINATION_REMOTE_WRITE_FAILED", exc.detail) from exc

        readback = self.observe()
        if readback.head_sha != commit_sha:
            raise CoordinationRemoteError(
                "COORDINATION_READBACK_MISMATCH",
                f"expected head {commit_sha}, observed {readback.head_sha}",
            )
        if readback.state != candidate:
            raise CoordinationRemoteError("COORDINATION_READBACK_MISMATCH", "state differs after ref update")
        return AppliedTransition(
            before_sha=observed.head_sha,
            after_sha=commit_sha,
            authority_now=observed.authority_now,
            state=copy.deepcopy(candidate),
            event=copy.deepcopy(event),
        )
