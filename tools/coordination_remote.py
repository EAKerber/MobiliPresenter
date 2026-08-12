from __future__ import annotations

import base64
import copy
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Protocol
from urllib.parse import quote

from tools import coordination

DEFAULT_REPOSITORY = "EAKerber/MobiliPresenter"
DEFAULT_AUTHORITY_BRANCH = "coordination/leases"
DEFAULT_STATE_PATH = "ops/coordination/leases.json"
DEFAULT_GH_TIMEOUT_SECONDS = 30
DEFAULT_READBACK_ATTEMPTS = 5
DEFAULT_READBACK_RETRY_SECONDS = 0.25
DEFAULT_TRANSIENT_ATTEMPTS = 3
DEFAULT_TRANSIENT_RETRY_SECONDS = 0.5
DEFAULT_REF_UPDATE_ATTEMPTS = 2
TRANSIENT_HTTP_STATUSES = {502, 503, 504}
GITOPS_COMMITTER_NAME = "MobiliPresenter GitOps"
GITOPS_COMMITTER_EMAIL = "gitops@mobilipresenter.local"


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

    The transport itself does one bounded process invocation. Higher-level
    authority code decides which operations are safe to retry. There is never
    a fallback to local time or a local coordination state.
    """

    def __init__(self, gh_executable: str = "gh", timeout_seconds: int = DEFAULT_GH_TIMEOUT_SECONDS) -> None:
        if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "timeout_seconds must be positive integer")
        self.gh_executable = gh_executable
        self.timeout_seconds = timeout_seconds

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
        try:
            proc = subprocess.run(
                command,
                input=json.dumps(payload, separators=(",", ":")) if payload is not None else None,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise CoordinationRemoteError(
                "COORDINATION_REMOTE_TIMEOUT",
                f"gh api exceeded {self.timeout_seconds}s for {method.upper()} {endpoint}",
            ) from exc
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


def _iso_git_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise CoordinationRemoteError("COORDINATION_TIME_UNAVAILABLE", "commit time must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GitHubCoordinationAuthority:
    def __init__(
        self,
        transport: Transport,
        *,
        repository: str = DEFAULT_REPOSITORY,
        authority_branch: str = DEFAULT_AUTHORITY_BRANCH,
        state_path: str = DEFAULT_STATE_PATH,
        readback_attempts: int = DEFAULT_READBACK_ATTEMPTS,
        readback_retry_seconds: float = DEFAULT_READBACK_RETRY_SECONDS,
        transient_attempts: int = DEFAULT_TRANSIENT_ATTEMPTS,
        transient_retry_seconds: float = DEFAULT_TRANSIENT_RETRY_SECONDS,
        ref_update_attempts: int = DEFAULT_REF_UPDATE_ATTEMPTS,
    ) -> None:
        if not isinstance(readback_attempts, int) or isinstance(readback_attempts, bool) or readback_attempts <= 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "readback_attempts must be positive integer")
        if not isinstance(readback_retry_seconds, (int, float)) or isinstance(readback_retry_seconds, bool) or readback_retry_seconds < 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "readback_retry_seconds must be non-negative")
        if not isinstance(transient_attempts, int) or isinstance(transient_attempts, bool) or transient_attempts <= 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "transient_attempts must be positive integer")
        if not isinstance(transient_retry_seconds, (int, float)) or isinstance(transient_retry_seconds, bool) or transient_retry_seconds < 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "transient_retry_seconds must be non-negative")
        if not isinstance(ref_update_attempts, int) or isinstance(ref_update_attempts, bool) or ref_update_attempts <= 0:
            raise CoordinationRemoteError("COORDINATION_REMOTE_CONFIG_INVALID", "ref_update_attempts must be positive integer")
        self.transport = transport
        self.repository = repository
        self.authority_branch = authority_branch
        self.state_path = state_path
        self.readback_attempts = readback_attempts
        self.readback_retry_seconds = float(readback_retry_seconds)
        self.transient_attempts = transient_attempts
        self.transient_retry_seconds = float(transient_retry_seconds)
        self.ref_update_attempts = ref_update_attempts

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

    @staticmethod
    def _is_transient_api_error(exc: ApiError) -> bool:
        return exc.status in TRANSIENT_HTTP_STATUSES

    def _request_retryable(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        include_headers: bool = False,
    ) -> ApiResponse:
        last: Exception | None = None
        for attempt in range(self.transient_attempts):
            try:
                return self.transport.request(
                    method,
                    endpoint,
                    payload=payload,
                    include_headers=include_headers,
                )
            except ApiError as exc:
                last = exc
                retryable = self._is_transient_api_error(exc)
            except CoordinationRemoteError as exc:
                last = exc
                retryable = exc.code == "COORDINATION_REMOTE_TIMEOUT"
            if not retryable or attempt + 1 >= self.transient_attempts:
                raise last
            if self.transient_retry_seconds:
                time.sleep(self.transient_retry_seconds)
        assert last is not None
        raise last

    def _read_ref(self) -> tuple[str, datetime]:
        response = self._request_retryable("GET", self._ref_endpoint, include_headers=True)
        payload = _json_body(response, operation="read authority ref")
        head_sha = _require_sha(
            payload.get("object", {}).get("sha") if isinstance(payload.get("object"), dict) else None,
            "authority head",
        )
        return head_sha, _server_time(response.headers)

    def _read_commit_tree(self, commit_sha: str) -> str:
        response = self._request_retryable("GET", f"repos/{self.repository}/git/commits/{commit_sha}")
        payload = _json_body(response, operation="read authority commit")
        return _require_sha(
            payload.get("tree", {}).get("sha") if isinstance(payload.get("tree"), dict) else None,
            "authority tree",
        )

    def _read_state(self, ref: str) -> dict[str, Any]:
        response = self._request_retryable("GET", self._state_endpoint(ref))
        payload = _json_body(response, operation="read coordination state")
        encoded = payload.get("content")
        encoding = payload.get("encoding")
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
        return state

    def observe(self) -> AuthorityObservation:
        try:
            head_sha, authority_now = self._read_ref()
            tree_sha = self._read_commit_tree(head_sha)
            state = self._read_state(head_sha)
            return AuthorityObservation(head_sha=head_sha, tree_sha=tree_sha, state=state, authority_now=authority_now)
        except CoordinationRemoteError:
            raise
        except ApiError as exc:
            raise CoordinationRemoteError("COORDINATION_REMOTE_UNAVAILABLE", exc.detail) from exc

    def _create_blob(self, content: str) -> str:
        response = self._request_retryable(
            "POST",
            f"repos/{self.repository}/git/blobs",
            payload={"content": content, "encoding": "utf-8"},
        )
        return _require_sha(_json_body(response, operation="create authority blob").get("sha"), "blob sha")

    def _create_tree(self, base_tree_sha: str, blob_sha: str) -> str:
        response = self._request_retryable(
            "POST",
            f"repos/{self.repository}/git/trees",
            payload={
                "base_tree": base_tree_sha,
                "tree": [{"path": self.state_path, "mode": "100644", "type": "blob", "sha": blob_sha}],
            },
        )
        return _require_sha(_json_body(response, operation="create authority tree").get("sha"), "tree sha")

    def _create_commit(self, parent_sha: str, tree_sha: str, message: str, authority_now: datetime) -> str:
        identity = {
            "name": GITOPS_COMMITTER_NAME,
            "email": GITOPS_COMMITTER_EMAIL,
            "date": _iso_git_time(authority_now),
        }
        payload = {
            "message": message,
            "tree": tree_sha,
            "parents": [parent_sha],
            "author": identity,
            "committer": identity,
        }
        response = self._request_retryable(
            "POST",
            f"repos/{self.repository}/git/commits",
            payload=payload,
        )
        return _require_sha(_json_body(response, operation="create authority commit").get("sha"), "commit sha")

    def _is_ancestor(self, ancestor_sha: str, head_sha: str) -> bool:
        if ancestor_sha == head_sha:
            return True
        response = self._request_retryable(
            "GET",
            f"repos/{self.repository}/compare/{ancestor_sha}...{head_sha}",
        )
        payload = _json_body(response, operation="compare authority ancestry")
        status = payload.get("status")
        merge_base = payload.get("merge_base_commit")
        merge_base_sha = merge_base.get("sha") if isinstance(merge_base, dict) else None
        return status in {"ahead", "identical"} and merge_base_sha == ancestor_sha

    def _ref_position(self, commit_sha: str, expected_parent_sha: str) -> str:
        current_sha, _ = self._read_ref()
        if current_sha == commit_sha or self._is_ancestor(commit_sha, current_sha):
            return "applied"
        if current_sha == expected_parent_sha or self._is_ancestor(current_sha, commit_sha):
            return "parent-or-stale"
        return "diverged"

    def _observe_ambiguous_ref_update(self, commit_sha: str, expected_parent_sha: str) -> str:
        last_position = "unknown"
        for attempt in range(self.readback_attempts):
            last_position = self._ref_position(commit_sha, expected_parent_sha)
            if last_position in {"applied", "diverged"}:
                return last_position
            if attempt + 1 < self.readback_attempts and self.readback_retry_seconds:
                time.sleep(self.readback_retry_seconds)
        return last_position

    def _advance_ref(self, commit_sha: str, expected_parent_sha: str) -> None:
        payload = {"sha": commit_sha, "force": False}
        last_transient: Exception | None = None
        for patch_attempt in range(self.ref_update_attempts):
            try:
                self.transport.request("PATCH", self._update_ref_endpoint, payload=payload)
                return
            except ApiError as exc:
                lowered = exc.detail.lower()
                if exc.status == 422 and ("fast forward" in lowered or "fast-forward" in lowered):
                    # A clean first-attempt 422 is definitive CAS loss. A 422 only
                    # becomes ambiguous after an earlier transient PATCH because that
                    # earlier request may have applied while its response was lost.
                    if patch_attempt == 0 and last_transient is None:
                        raise CoordinationRemoteError(
                            "COORDINATION_REF_DRIFT",
                            "authority advanced after observation",
                        ) from exc
                    position = self._observe_ambiguous_ref_update(commit_sha, expected_parent_sha)
                    if position == "applied":
                        return
                    raise CoordinationRemoteError("COORDINATION_REF_DRIFT", "authority advanced to a competing history") from exc
                if not self._is_transient_api_error(exc):
                    raise CoordinationRemoteError("COORDINATION_REMOTE_WRITE_FAILED", exc.detail) from exc
                last_transient = exc
            except CoordinationRemoteError as exc:
                if exc.code != "COORDINATION_REMOTE_TIMEOUT":
                    raise
                last_transient = exc

            position = self._observe_ambiguous_ref_update(commit_sha, expected_parent_sha)
            if position == "applied":
                return
            if position == "diverged":
                raise CoordinationRemoteError("COORDINATION_REF_DRIFT", "authority diverged during ambiguous ref update") from last_transient
            if patch_attempt + 1 < self.ref_update_attempts:
                if self.transient_retry_seconds:
                    time.sleep(self.transient_retry_seconds)
                continue
            detail = getattr(last_transient, "detail", str(last_transient))
            raise CoordinationRemoteError(
                "COORDINATION_REMOTE_WRITE_FAILED",
                f"ambiguous ref update remained at observed parent after retries: {detail}",
            ) from last_transient

    def _verify_published_transition(self, commit_sha: str, candidate: dict[str, Any]) -> None:
        try:
            state_at_commit = self._read_state(commit_sha)
            if state_at_commit != candidate:
                raise CoordinationRemoteError(
                    "COORDINATION_READBACK_MISMATCH",
                    f"state at published commit {commit_sha} differs from candidate",
                )

            last_head: str | None = None
            for attempt in range(self.readback_attempts):
                current = self.observe()
                last_head = current.head_sha
                if self._is_ancestor(commit_sha, current.head_sha):
                    return
                if self._is_ancestor(current.head_sha, commit_sha):
                    if attempt + 1 < self.readback_attempts and self.readback_retry_seconds:
                        time.sleep(self.readback_retry_seconds)
                    continue
                raise CoordinationRemoteError(
                    "COORDINATION_READBACK_MISMATCH",
                    f"published commit {commit_sha} diverges from current head {current.head_sha}",
                )

            raise CoordinationRemoteError(
                "COORDINATION_READBACK_STALE",
                f"published commit {commit_sha} not visible at ref after {self.readback_attempts} observations; last head {last_head}",
            )
        except CoordinationRemoteError:
            raise
        except ApiError as exc:
            raise CoordinationRemoteError("COORDINATION_REMOTE_UNAVAILABLE", exc.detail) from exc

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
            commit_sha = self._create_commit(observed.head_sha, tree_sha, message.strip(), observed.authority_now)
            self._advance_ref(commit_sha, observed.head_sha)
        except CoordinationRemoteError:
            raise
        except ApiError as exc:
            raise CoordinationRemoteError("COORDINATION_REMOTE_WRITE_FAILED", exc.detail) from exc

        self._verify_published_transition(commit_sha, candidate)
        return AppliedTransition(
            before_sha=observed.head_sha,
            after_sha=commit_sha,
            authority_now=observed.authority_now,
            state=copy.deepcopy(candidate),
            event=copy.deepcopy(event),
        )
