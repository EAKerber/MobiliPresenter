"""Git-backed executor for live ContinuationState using Transition Protocol 0.1."""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from tools import continuation
from tools import continuation_transition as transition
from tools import transition_protocol as protocol
from tools.coordination_remote import ApiError, GhApiTransport

DEFAULT_REPOSITORY = "EAKerber/MobiliPresenter"
DEFAULT_BRANCH = "coordination/continuations"
DEFAULT_DIR = "ops/continuations"
DEFAULT_READBACK_ATTEMPTS = 5
DEFAULT_READBACK_RETRY_SECONDS = 0.25


class ContinuationRemoteError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass(frozen=True)
class Observation:
    head_sha: str
    tree_sha: str
    items: dict[str, dict[str, Any]]


class GitHubContinuationAuthority:
    def __init__(
        self,
        transport=None,
        repository: str = DEFAULT_REPOSITORY,
        authority_branch: str = DEFAULT_BRANCH,
        state_dir: str = DEFAULT_DIR,
        readback_attempts: int = DEFAULT_READBACK_ATTEMPTS,
        readback_retry_seconds: float = DEFAULT_READBACK_RETRY_SECONDS,
    ) -> None:
        self.transport = transport or GhApiTransport()
        self.repository = repository
        self.authority_branch = authority_branch
        self.state_dir = state_dir
        self.readback_attempts = readback_attempts
        self.readback_retry_seconds = readback_retry_seconds

    @property
    def ref_endpoint(self) -> str:
        return f"repos/{self.repository}/git/ref/heads/{quote(self.authority_branch, safe='')}"

    @property
    def update_endpoint(self) -> str:
        return f"repos/{self.repository}/git/refs/heads/{quote(self.authority_branch, safe='')}"

    def _json(self, response, operation: str) -> Any:
        try:
            return json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE", operation) from exc

    def _sha(self, value: Any, label: str) -> str:
        if not isinstance(value, str) or len(value) != 40:
            raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE", label)
        return value

    def _head(self) -> str:
        try:
            payload = self._json(self.transport.request("GET", self.ref_endpoint), "read ref")
        except ApiError as exc:
            raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE", exc.detail) from exc
        return self._sha((payload.get("object") or {}).get("sha"), "head")

    def _tree(self, head: str) -> str:
        payload = self._json(self.transport.request("GET", f"repos/{self.repository}/git/commits/{head}"), "read commit")
        return self._sha((payload.get("tree") or {}).get("sha"), "tree")

    def _task_endpoint(self, cid: str, ref: str) -> str:
        return f"repos/{self.repository}/contents/{quote(self.state_dir, safe='/')}/{quote(cid + '.json', safe='')}?ref={quote(ref, safe='')}"

    def _read_task(self, cid: str, ref: str) -> dict[str, Any] | None:
        try:
            response = self.transport.request("GET", self._task_endpoint(cid, ref))
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE", exc.detail) from exc
        payload = self._json(response, "read task")
        encoded = payload.get("content")
        if not isinstance(encoded, str) or payload.get("encoding") != "base64":
            raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE", "task content")
        try:
            value = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception as exc:
            raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_STATE", cid) from exc
        errors = continuation.validate(value, cid)
        if errors:
            raise ContinuationRemoteError(errors[0], cid)
        return value

    def observe(self) -> Observation:
        head = self._head()
        tree = self._tree(head)
        endpoint = f"repos/{self.repository}/contents/{quote(self.state_dir, safe='/')}?ref={quote(head, safe='')}"
        try:
            response = self.transport.request("GET", endpoint)
            listing = self._json(response, "list continuations")
        except ApiError as exc:
            if exc.status == 404:
                return Observation(head, tree, {})
            raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE", exc.detail) from exc
        if not isinstance(listing, list):
            raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE", "directory listing")
        items: dict[str, dict[str, Any]] = {}
        for entry in listing:
            name = entry.get("name") if isinstance(entry, dict) else None
            if isinstance(name, str) and name.endswith(".json") and not name.startswith("."):
                cid = name[:-5]
                value = self._read_task(cid, head)
                if value is not None:
                    items[cid] = value
        return Observation(head, tree, items)

    def apply(self, planned: dict[str, Any], expected_plan: str | None) -> dict[str, Any]:
        try:
            transition.validate_plan(
                planned,
                repository=self.repository,
                authority_branch=self.authority_branch,
                state_dir=self.state_dir,
            )
            protocol.require_expected_plan(planned, expected_plan)
        except RuntimeError as exc:
            raise ContinuationRemoteError(str(exc).split(":", 1)[0]) from exc

        cid = planned["subject"]["id"]
        observed = self.observe()
        current = observed.items.get(cid)
        if continuation.state_hash(current) != planned["beforeStateHash"]:
            raise ContinuationRemoteError("CONTINUATION_PLAN_STALE")
        try:
            transition.validate_plan(
                planned,
                current,
                repository=self.repository,
                authority_branch=self.authority_branch,
                state_dir=self.state_dir,
                bind_before=True,
            )
        except RuntimeError as exc:
            code = str(exc).split(":", 1)[0]
            if code == "CONTINUATION_PLAN_STALE":
                raise ContinuationRemoteError(code) from exc
            raise ContinuationRemoteError("CONTINUATION_PLAN_INVALID", code) from exc

        content = json.dumps(planned["candidate"], indent=2, ensure_ascii=False) + "\n"
        blob = self._sha(
            self._json(
                self.transport.request(
                    "POST",
                    f"repos/{self.repository}/git/blobs",
                    payload={"content": content, "encoding": "utf-8"},
                ),
                "create blob",
            ).get("sha"),
            "blob",
        )
        path = f"{self.state_dir}/{cid}.json"
        tree_payload = {
            "base_tree": observed.tree_sha,
            "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob}],
        }
        tree = self._sha(
            self._json(
                self.transport.request("POST", f"repos/{self.repository}/git/trees", payload=tree_payload),
                "create tree",
            ).get("sha"),
            "tree",
        )
        commit_payload = {
            "message": f"continuation: {planned['action']} {cid}",
            "tree": tree,
            "parents": [observed.head_sha],
        }
        commit = self._sha(
            self._json(
                self.transport.request("POST", f"repos/{self.repository}/git/commits", payload=commit_payload),
                "create commit",
            ).get("sha"),
            "commit",
        )
        try:
            self.transport.request("PATCH", self.update_endpoint, payload={"sha": commit, "force": False})
        except ApiError as exc:
            raise ContinuationRemoteError("CONTINUATION_CAS_LOST", exc.detail) from exc

        last: Observation | None = None
        for attempt in range(self.readback_attempts):
            readback = self.observe()
            last = readback
            value = readback.items.get(cid)
            if continuation.state_hash(value) == planned["afterStateHash"]:
                try:
                    receipt = protocol.build_receipt(planned, value, authority_revision=readback.head_sha)
                    protocol.validate_receipt(receipt, planned)
                    return receipt
                except RuntimeError as exc:
                    raise ContinuationRemoteError("CONTINUATION_RECEIPT_INVALID", str(exc)) from exc
            if attempt + 1 < self.readback_attempts:
                time.sleep(self.readback_retry_seconds)
        if last is not None and last.head_sha == observed.head_sha:
            raise ContinuationRemoteError("CONTINUATION_READBACK_HEAD_STALE")
        raise ContinuationRemoteError("CONTINUATION_READBACK_STATE_MISMATCH")
