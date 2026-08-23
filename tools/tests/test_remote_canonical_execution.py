from __future__ import annotations

import base64
import copy
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from tools import continuation_transition
from tools import remote_canonical
from tools import remote_canonical_execution as bridge
from tools import transition_protocol
from tools.coordination_remote import ApiError, ApiResponse

HEAD = "a" * 40
BASE_TREE = "b" * 40
OLD_CONTENT = "before\n"
NEW_CONTENT = "after\n"
OLD_BLOB = hashlib.sha1(
    f"blob {len(OLD_CONTENT.encode('utf-8'))}\0".encode("ascii")
    + OLD_CONTENT.encode("utf-8")
).hexdigest()
SOURCE = {
    "workflow": "remote-canonical-execution",
    "sourceSha": "f" * 40,
    "runId": "123",
    "issueNumber": 7,
    "commentId": 11,
}
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-primary",
    "sessionId": "rp1b-test-session",
}


def git_command(operation="update-file", *, expected_head=HEAD, branch="work/operations/rp1b-test"):
    target = {"operation": operation, "branch": branch}
    expected = {}
    payload = {}
    if operation == "create-branch":
        expected = {"baseSha": HEAD}
    else:
        target["path"] = "probe.txt"
        if operation == "create-file":
            expected = {"branchHead": expected_head}
            payload = {"content": NEW_CONTENT, "message": "probe create"}
        elif operation == "update-file":
            expected = {"branchHead": expected_head, "blobSha": OLD_BLOB}
            payload = {"content": NEW_CONTENT, "message": "probe update"}
        else:
            expected = {"branchHead": expected_head, "blobSha": OLD_BLOB}
            payload = {"message": "probe delete"}
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": f"rp1b-{operation}",
        "kind": "git-direct",
        "actor": ACTOR,
        "declaredIntent": {"goal": "qualify remote canonical execution"},
        "target": target,
        "expected": expected,
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def continuation_command():
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "rp1b-continuation-create",
        "kind": "domain",
        "actor": ACTOR,
        "declaredIntent": {"goal": "prove domain delegation"},
        "target": {
            "domain": "continuation",
            "action": "create",
            "subject": {"kind": "continuation", "id": "rp1b-domain-test"},
        },
        "expected": {"authorityRevision": HEAD},
        "payload": {
            "workerId": "manager-gitops-primary",
            "remaining": ["finish"],
            "nextAction": "finish",
            "branch": "work/operations/rp1b-domain-test",
            "prNumber": None,
            "dependsOn": [],
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class FakeGitTransport:
    def __init__(self):
        self.refs = {"work/operations/rp1b-test": HEAD}
        self.blobs = {OLD_BLOB: OLD_CONTENT}
        self.trees = {
            BASE_TREE: [{"path": "probe.txt", "type": "blob", "sha": OLD_BLOB}]
        }
        self.commits = {HEAD: {"tree": BASE_TREE, "parents": []}}
        self.mutable_calls = []
        self._tree_counter = 0
        self._commit_counter = 0

    def _response(self, value, status=200):
        return ApiResponse(status=status, headers={}, body=json.dumps(value))

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        method = method.upper()
        if method in {"POST", "PATCH", "PUT", "DELETE"}:
            self.mutable_calls.append((method, endpoint, copy.deepcopy(payload)))

        prefix = f"repos/{bridge.REPOSITORY}/"
        if not endpoint.startswith(prefix):
            raise AssertionError(endpoint)
        path = endpoint[len(prefix):]

        if method == "GET" and path.startswith("git/ref/heads/"):
            branch = path[len("git/ref/heads/"):]
            from urllib.parse import unquote
            branch = unquote(branch)
            if branch not in self.refs:
                raise ApiError(404, "not found")
            return self._response({"object": {"sha": self.refs[branch]}})

        if method == "GET" and path.startswith("git/commits/"):
            sha = path[len("git/commits/"):]
            if sha not in self.commits:
                raise ApiError(404, "commit not found")
            item = self.commits[sha]
            return self._response({
                "sha": sha,
                "tree": {"sha": item["tree"]},
                "parents": [{"sha": parent} for parent in item["parents"]],
            })

        if method == "GET" and path.startswith("git/trees/"):
            tree_sha = path[len("git/trees/"):].split("?", 1)[0]
            if tree_sha not in self.trees:
                raise ApiError(404, "tree not found")
            return self._response({
                "sha": tree_sha,
                "truncated": False,
                "tree": copy.deepcopy(self.trees[tree_sha]),
            })

        if method == "GET" and path.startswith("contents/"):
            raw, ref = path[len("contents/"):].split("?ref=", 1)
            from urllib.parse import unquote
            file_path = unquote(raw)
            ref = unquote(ref)
            commit = self.commits.get(ref)
            if commit is None:
                raise ApiError(404, "ref not found")
            entries = self.trees[commit["tree"]]
            match = [
                item for item in entries
                if item.get("type") == "blob" and item.get("path") == file_path
            ]
            if not match:
                raise ApiError(404, "file not found")
            content = self.blobs[match[0]["sha"]]
            return self._response({
                "encoding": "base64",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            })

        if method == "POST" and path == "git/blobs":
            content = payload["content"]
            raw = content.encode("utf-8")
            sha = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
            self.blobs[sha] = content
            return self._response({"sha": sha}, 201)

        if method == "POST" and path == "git/trees":
            base = copy.deepcopy(self.trees[payload["base_tree"]])
            by_path = {item["path"]: item for item in base}
            for item in payload["tree"]:
                if item["sha"] is None:
                    by_path.pop(item["path"], None)
                else:
                    by_path[item["path"]] = {
                        "path": item["path"],
                        "type": "blob",
                        "sha": item["sha"],
                    }
            self._tree_counter += 1
            sha = f"{self._tree_counter:040x}"
            self.trees[sha] = [by_path[key] for key in sorted(by_path)]
            return self._response({"sha": sha}, 201)

        if method == "POST" and path == "git/commits":
            self._commit_counter += 1
            sha = f"{1000 + self._commit_counter:040x}"
            self.commits[sha] = {
                "tree": payload["tree"],
                "parents": list(payload["parents"]),
            }
            return self._response({"sha": sha}, 201)

        if method == "PATCH" and path.startswith("git/refs/heads/"):
            from urllib.parse import unquote
            branch = unquote(path[len("git/refs/heads/"):])
            if payload.get("force") is not False:
                raise AssertionError("force must remain false")
            current = self.refs.get(branch)
            new = payload["sha"]
            if current is None or self.commits[new]["parents"] != [current]:
                raise ApiError(422, "non-fast-forward")
            self.refs[branch] = new
            return self._response({"object": {"sha": new}})

        if method == "POST" and path == "git/refs":
            ref = payload["ref"]
            if not ref.startswith("refs/heads/"):
                raise AssertionError(ref)
            branch = ref[len("refs/heads/"):]
            if branch in self.refs:
                raise ApiError(422, "already exists")
            self.refs[branch] = payload["sha"]
            return self._response({"ref": ref, "object": {"sha": payload["sha"]}}, 201)

        raise AssertionError(f"unsupported {method} {endpoint}")


class FakeContinuationAuthority:
    def __init__(self, transport=None):
        self.transport = transport
        self.applied = []

    def observe(self):
        return SimpleNamespace(head_sha=HEAD, tree_sha=BASE_TREE, items={})

    def apply(self, plan, expected_plan):
        transition_protocol.require_expected_plan(plan, expected_plan)
        continuation_transition.validate_plan(
            plan, None, bind_before=True, inventory=[]
        )
        self.applied.append(plan)
        receipt = transition_protocol.build_receipt(
            plan, plan["candidate"], authority_revision="c" * 40
        )
        transition_protocol.validate_receipt(receipt, plan)
        return receipt


class RemoteCanonicalExecutionTests(unittest.TestCase):
    def test_command_is_closed_non_authoritative_and_deterministic(self):
        command = git_command()
        self.assertEqual(bridge.validate_command(command), command)
        self.assertEqual(bridge.command_hash(command), bridge.command_hash(copy.deepcopy(command)))
        self.assertFalse(command["semanticAuthority"])
        self.assertFalse(command["authorizesMutation"])

    def test_control_branch_is_rejected_before_transport(self):
        command = git_command(branch="main")
        with self.assertRaisesRegex(RuntimeError, "CONTROL_BRANCH_FORBIDDEN"):
            bridge.validate_command(command)

    def test_stale_head_blocks_before_any_mutable_git_call(self):
        transport = FakeGitTransport()
        command = git_command(expected_head="e" * 40)
        with self.assertRaisesRegex(RuntimeError, "REMOTE_GIT_PLAN_STALE"):
            bridge.execute_command(command, source=SOURCE, transport=transport)
        self.assertEqual(transport.mutable_calls, [])

    def test_update_file_uses_plan_bundle_nonforce_ref_and_aggregate_readback(self):
        transport = FakeGitTransport()
        command = git_command()
        receipt = bridge.execute_command(command, source=SOURCE, transport=transport)
        bridge.validate_receipt(receipt)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["route"], {
            "kind": "git-direct", "domain": "git", "action": "update-file"
        })
        self.assertEqual(receipt["aggregateReadback"]["changedPaths"], ["probe.txt"])
        self.assertEqual(
            receipt["evidence"]["bundle"]["entries"][0]["contentSha256"],
            hashlib.sha256(NEW_CONTENT.encode("utf-8")).hexdigest(),
        )
        methods = [item[0] for item in transport.mutable_calls]
        self.assertEqual(methods, ["POST", "POST", "POST", "PATCH"])
        patch = transport.mutable_calls[-1]
        self.assertIs(patch[2]["force"], False)
        self.assertNotIn("contents/", "\n".join(item[1] for item in transport.mutable_calls))

    def test_replay_is_at_most_once_by_expected_head(self):
        transport = FakeGitTransport()
        command = git_command()
        first = bridge.execute_command(command, source=SOURCE, transport=transport)
        self.assertEqual(first["status"], "PASS")
        mutable_count = len(transport.mutable_calls)
        with self.assertRaisesRegex(RuntimeError, "REMOTE_GIT_PLAN_STALE"):
            bridge.execute_command(command, source=SOURCE, transport=transport)
        self.assertEqual(len(transport.mutable_calls), mutable_count)

    def test_create_branch_requires_absence_and_reads_back_exact_sha(self):
        transport = FakeGitTransport()
        command = git_command("create-branch", branch="work/operations/rp1b-new")
        receipt = bridge.execute_command(command, source=SOURCE, transport=transport)
        self.assertEqual(receipt["aggregateReadback"], {
            "kind": "branch-head",
            "branch": "work/operations/rp1b-new",
            "head": HEAD,
            "status": "PASS",
        })
        self.assertEqual(transport.refs["work/operations/rp1b-new"], HEAD)

    def test_domain_route_reuses_remote_request_and_canonical_continuation_writer(self):
        command = continuation_command()
        fake = FakeContinuationAuthority()
        with mock.patch.object(
            bridge.continuation_remote,
            "GitHubContinuationAuthority",
            return_value=fake,
        ):
            receipt = bridge.execute_command(command, source=SOURCE, transport=object())
        bridge.validate_receipt(receipt)
        self.assertEqual(receipt["route"]["domain"], "continuation")
        self.assertEqual(receipt["evidence"]["request"]["schemaVersion"], remote_canonical.REQUEST_SCHEMA)
        self.assertEqual(len(fake.applied), 1)
        self.assertEqual(fake.applied[0], receipt["evidence"]["plan"])

    def test_receipt_tampering_is_rejected(self):
        transport = FakeGitTransport()
        receipt = bridge.execute_command(git_command(), source=SOURCE, transport=transport)
        receipt["aggregateReadback"]["status"] = "UNKNOWN"
        with self.assertRaisesRegex(RuntimeError, "MISMATCH|HASH"):
            bridge.validate_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
