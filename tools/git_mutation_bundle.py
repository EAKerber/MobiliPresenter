#!/usr/bin/env python3
"""Deterministic contract for atomic multi-path Git mutations.

The bundle is read-only intent/evidence. It never authorizes or performs a mutation.
Providers may materialize a candidate tree/commit/ref only after the bundle and the
candidate tree have been validated, then prove the published result by readback.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash

SCHEMA_VERSION = "GitMutationBundle 0.1"
TREE_PROOF_SCHEMA = "GitMutationTreeProof 0.1"
READBACK_SCHEMA = "GitMutationBundleReadback 0.1"
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPERATIONS = {"write", "delete"}
ATOMIC_PROFILE_REQUIRED_FEATURES = (
    "commit-create-with-parent",
    "content-readback",
    "non-force-ref-update",
    "ref-create-at-commit",
    "ref-read",
    "tree-create-inline-content",
    "tree-readback",
)
BUNDLE_FIELDS = {
    "schemaVersion",
    "repository",
    "branch",
    "baseHead",
    "baseTreeSha",
    "refPrecondition",
    "entries",
    "expectedChangedPaths",
    "force",
    "authorizesMutation",
    "bundleHash",
}
ENTRY_FIELDS = {
    "path",
    "operation",
    "contentSha256",
    "gitBlobSha",
    "sizeBytes",
}


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _git_sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _sha256(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _path(value: Any) -> str:
    path = _nonempty(value, "GIT_MUTATION_BUNDLE_PATH_REQUIRED")
    if path.startswith("/") or path.endswith("/") or ".." in path.split("/"):
        raise RuntimeError("GIT_MUTATION_BUNDLE_PATH_INVALID")
    if "\\" in path:
        raise RuntimeError("GIT_MUTATION_BUNDLE_PATH_INVALID")
    return path


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _content_metadata(content: str) -> tuple[str, str, int]:
    if not isinstance(content, str):
        raise RuntimeError("GIT_MUTATION_BUNDLE_CONTENT_MUST_BE_UTF8_TEXT")
    raw = content.encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), _git_blob_sha(raw), len(raw)


def provider_satisfies_atomic_profile(provider: Any) -> bool:
    """Return whether a normalized provider record proves the atomic profile.

    Provider identity is intentionally irrelevant. Only observed PASS + features
    matter, preserving the capability/provider separation.
    """
    if not isinstance(provider, dict):
        return False
    if str(provider.get("status") or "").upper() != "PASS":
        return False
    features = provider.get("features")
    if not isinstance(features, list) or any(not isinstance(item, str) for item in features):
        return False
    return set(ATOMIC_PROFILE_REQUIRED_FEATURES).issubset(set(features))


def build_bundle(
    *,
    repository: str,
    branch: str,
    base_head: str,
    base_tree_sha: str,
    changes: list[dict[str, Any]],
    current_branch_head: str | None = None,
) -> dict[str, Any]:
    repository = _nonempty(repository, "GIT_MUTATION_BUNDLE_REPOSITORY_REQUIRED")
    branch = _nonempty(branch, "GIT_MUTATION_BUNDLE_BRANCH_REQUIRED")
    base_head = _git_sha(base_head, "GIT_MUTATION_BUNDLE_BASE_HEAD_INVALID")
    base_tree_sha = _git_sha(base_tree_sha, "GIT_MUTATION_BUNDLE_BASE_TREE_INVALID")
    if current_branch_head is None:
        ref_precondition = {"kind": "absent"}
    else:
        current_branch_head = _git_sha(current_branch_head, "GIT_MUTATION_BUNDLE_REF_HEAD_INVALID")
        if current_branch_head != base_head:
            raise RuntimeError("GIT_MUTATION_BUNDLE_REF_BASE_MISMATCH")
        ref_precondition = {"kind": "head", "sha": current_branch_head}
    if not isinstance(changes, list) or not changes:
        raise RuntimeError("GIT_MUTATION_BUNDLE_CHANGES_REQUIRED")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in changes:
        if not isinstance(raw, dict):
            raise RuntimeError("GIT_MUTATION_BUNDLE_CHANGE_INVALID")
        path = _path(raw.get("path"))
        if path in seen:
            raise RuntimeError(f"GIT_MUTATION_BUNDLE_DUPLICATE_PATH:{path}")
        seen.add(path)
        delete = raw.get("delete", False)
        if delete is True:
            if set(raw) != {"path", "delete"}:
                raise RuntimeError("GIT_MUTATION_BUNDLE_DELETE_FIELDS_INVALID")
            entry = {
                "path": path,
                "operation": "delete",
                "contentSha256": None,
                "gitBlobSha": None,
                "sizeBytes": 0,
            }
        else:
            if set(raw) != {"path", "content"}:
                raise RuntimeError("GIT_MUTATION_BUNDLE_WRITE_FIELDS_INVALID")
            digest, blob_sha, size = _content_metadata(raw.get("content"))
            entry = {
                "path": path,
                "operation": "write",
                "contentSha256": digest,
                "gitBlobSha": blob_sha,
                "sizeBytes": size,
            }
        entries.append(entry)

    entries.sort(key=lambda item: item["path"])
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": repository,
        "branch": branch,
        "baseHead": base_head,
        "baseTreeSha": base_tree_sha,
        "refPrecondition": ref_precondition,
        "entries": entries,
        "expectedChangedPaths": [item["path"] for item in entries],
        "force": False,
        "authorizesMutation": False,
    }
    return {**core, "bundleHash": stable_hash(core)}


def _validate_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != ENTRY_FIELDS:
        raise RuntimeError("GIT_MUTATION_BUNDLE_ENTRY_FIELDS_INVALID")
    path = _path(raw["path"])
    operation = raw["operation"]
    if operation not in OPERATIONS:
        raise RuntimeError("GIT_MUTATION_BUNDLE_OPERATION_INVALID")
    size = raw["sizeBytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise RuntimeError("GIT_MUTATION_BUNDLE_SIZE_INVALID")
    if operation == "write":
        digest = _sha256(raw["contentSha256"], "GIT_MUTATION_BUNDLE_CONTENT_HASH_INVALID")
        blob_sha = _git_sha(raw["gitBlobSha"], "GIT_MUTATION_BUNDLE_BLOB_SHA_INVALID")
        return {
            "path": path,
            "operation": operation,
            "contentSha256": digest,
            "gitBlobSha": blob_sha,
            "sizeBytes": size,
        }
    if raw["contentSha256"] is not None or raw["gitBlobSha"] is not None or size != 0:
        raise RuntimeError("GIT_MUTATION_BUNDLE_DELETE_METADATA_INVALID")
    return {
        "path": path,
        "operation": operation,
        "contentSha256": None,
        "gitBlobSha": None,
        "sizeBytes": 0,
    }


def validate_bundle(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BUNDLE_FIELDS:
        raise RuntimeError("GIT_MUTATION_BUNDLE_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("GIT_MUTATION_BUNDLE_SCHEMA_UNSUPPORTED")
    repository = _nonempty(value.get("repository"), "GIT_MUTATION_BUNDLE_REPOSITORY_REQUIRED")
    branch = _nonempty(value.get("branch"), "GIT_MUTATION_BUNDLE_BRANCH_REQUIRED")
    base_head = _git_sha(value.get("baseHead"), "GIT_MUTATION_BUNDLE_BASE_HEAD_INVALID")
    base_tree = _git_sha(value.get("baseTreeSha"), "GIT_MUTATION_BUNDLE_BASE_TREE_INVALID")
    ref_pre = value.get("refPrecondition")
    if not isinstance(ref_pre, dict) or ref_pre.get("kind") not in {"absent", "head"}:
        raise RuntimeError("GIT_MUTATION_BUNDLE_REF_PRECONDITION_INVALID")
    if ref_pre.get("kind") == "absent":
        if set(ref_pre) != {"kind"}:
            raise RuntimeError("GIT_MUTATION_BUNDLE_REF_PRECONDITION_INVALID")
        ref_precondition = {"kind": "absent"}
    else:
        if set(ref_pre) != {"kind", "sha"}:
            raise RuntimeError("GIT_MUTATION_BUNDLE_REF_PRECONDITION_INVALID")
        ref_sha = _git_sha(ref_pre.get("sha"), "GIT_MUTATION_BUNDLE_REF_HEAD_INVALID")
        if ref_sha != base_head:
            raise RuntimeError("GIT_MUTATION_BUNDLE_REF_BASE_MISMATCH")
        ref_precondition = {"kind": "head", "sha": ref_sha}
    if value.get("force") is not False:
        raise RuntimeError("GIT_MUTATION_BUNDLE_FORCE_FORBIDDEN")
    if value.get("authorizesMutation") is not False:
        raise RuntimeError("GIT_MUTATION_BUNDLE_MUST_NOT_AUTHORIZE")
    entries_raw = value.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise RuntimeError("GIT_MUTATION_BUNDLE_ENTRIES_REQUIRED")
    entries = [_validate_entry(item) for item in entries_raw]
    paths = [item["path"] for item in entries]
    if len(set(paths)) != len(paths):
        raise RuntimeError("GIT_MUTATION_BUNDLE_DUPLICATE_PATH")
    if paths != sorted(paths):
        raise RuntimeError("GIT_MUTATION_BUNDLE_ENTRIES_NOT_CANONICAL")
    expected = value.get("expectedChangedPaths")
    if expected != paths:
        raise RuntimeError("GIT_MUTATION_BUNDLE_CHANGED_PATHS_MISMATCH")
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": repository,
        "branch": branch,
        "baseHead": base_head,
        "baseTreeSha": base_tree,
        "refPrecondition": ref_precondition,
        "entries": entries,
        "expectedChangedPaths": paths,
        "force": False,
        "authorizesMutation": False,
    }
    if value.get("bundleHash") != stable_hash(core):
        raise RuntimeError("GIT_MUTATION_BUNDLE_HASH_MISMATCH")
    if value != {**core, "bundleHash": value["bundleHash"]}:
        raise RuntimeError("GIT_MUTATION_BUNDLE_NOT_CANONICAL")
    return value


def verify_materialized_content(bundle: dict[str, Any], content_by_path: dict[str, str]) -> None:
    """Bind concrete UTF-8 content to the metadata declared by the bundle."""
    validate_bundle(bundle)
    if not isinstance(content_by_path, dict):
        raise RuntimeError("GIT_MUTATION_BUNDLE_CONTENT_MAP_INVALID")
    expected_write_paths = {
        item["path"] for item in bundle["entries"] if item["operation"] == "write"
    }
    if set(content_by_path) != expected_write_paths:
        raise RuntimeError("GIT_MUTATION_BUNDLE_CONTENT_COVERAGE_MISMATCH")
    for entry in bundle["entries"]:
        if entry["operation"] != "write":
            continue
        digest, blob_sha, size = _content_metadata(content_by_path[entry["path"]])
        if (
            digest != entry["contentSha256"]
            or blob_sha != entry["gitBlobSha"]
            or size != entry["sizeBytes"]
        ):
            raise RuntimeError(f"GIT_MUTATION_BUNDLE_CONTENT_MISMATCH:{entry['path']}")


def _blob_map(tree_entries: Any) -> dict[str, str]:
    if not isinstance(tree_entries, list):
        raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_ENTRIES_INVALID")
    result: dict[str, str] = {}
    for item in tree_entries:
        if not isinstance(item, dict):
            raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_ENTRY_INVALID")
        if item.get("type") != "blob":
            continue
        path = _path(item.get("path"))
        sha = _git_sha(item.get("sha"), "GIT_MUTATION_BUNDLE_TREE_BLOB_SHA_INVALID")
        if path in result:
            raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_DUPLICATE_PATH")
        result[path] = sha
    return result


def verify_tree(
    bundle: dict[str, Any],
    *,
    base_tree_entries: list[dict[str, Any]],
    candidate_tree_entries: list[dict[str, Any]],
    candidate_tree_sha: str,
) -> dict[str, Any]:
    validate_bundle(bundle)
    candidate_tree_sha = _git_sha(candidate_tree_sha, "GIT_MUTATION_BUNDLE_CANDIDATE_TREE_INVALID")
    base = _blob_map(base_tree_entries)
    candidate = _blob_map(candidate_tree_entries)
    changed = sorted(
        path for path in (set(base) | set(candidate)) if base.get(path) != candidate.get(path)
    )
    if changed != bundle["expectedChangedPaths"]:
        raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_CHANGED_PATHS_MISMATCH")
    for entry in bundle["entries"]:
        path = entry["path"]
        if entry["operation"] == "write":
            if candidate.get(path) != entry["gitBlobSha"]:
                raise RuntimeError(f"GIT_MUTATION_BUNDLE_TREE_BLOB_MISMATCH:{path}")
        elif path in candidate:
            raise RuntimeError(f"GIT_MUTATION_BUNDLE_TREE_DELETE_MISMATCH:{path}")
    core = {
        "schemaVersion": TREE_PROOF_SCHEMA,
        "bundleHash": bundle["bundleHash"],
        "baseTreeSha": bundle["baseTreeSha"],
        "candidateTreeSha": candidate_tree_sha,
        "changedPaths": changed,
        "status": "PASS",
    }
    return {**core, "proofHash": stable_hash(core)}


def validate_tree_proof(bundle: dict[str, Any], proof: Any) -> dict[str, Any]:
    validate_bundle(bundle)
    required = {
        "schemaVersion",
        "bundleHash",
        "baseTreeSha",
        "candidateTreeSha",
        "changedPaths",
        "status",
        "proofHash",
    }
    if not isinstance(proof, dict) or set(proof) != required:
        raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_PROOF_FIELDS_INVALID")
    candidate = _git_sha(proof.get("candidateTreeSha"), "GIT_MUTATION_BUNDLE_CANDIDATE_TREE_INVALID")
    core = {
        "schemaVersion": TREE_PROOF_SCHEMA,
        "bundleHash": bundle["bundleHash"],
        "baseTreeSha": bundle["baseTreeSha"],
        "candidateTreeSha": candidate,
        "changedPaths": bundle["expectedChangedPaths"],
        "status": "PASS",
    }
    expected = {**core, "proofHash": stable_hash(core)}
    if proof != expected:
        raise RuntimeError("GIT_MUTATION_BUNDLE_TREE_PROOF_MISMATCH")
    return proof


def verify_readback(bundle: dict[str, Any], receipt: Any) -> dict[str, Any]:
    validate_bundle(bundle)
    required = {
        "branchHead",
        "commitSha",
        "parentSha",
        "treeSha",
        "changedPaths",
        "contentSha256",
        "treeProof",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_FIELDS_INVALID")
    branch_head = _git_sha(receipt["branchHead"], "GIT_MUTATION_BUNDLE_READBACK_REF_INVALID")
    commit_sha = _git_sha(receipt["commitSha"], "GIT_MUTATION_BUNDLE_READBACK_COMMIT_INVALID")
    parent_sha = _git_sha(receipt["parentSha"], "GIT_MUTATION_BUNDLE_READBACK_PARENT_INVALID")
    tree_sha = _git_sha(receipt["treeSha"], "GIT_MUTATION_BUNDLE_READBACK_TREE_INVALID")
    tree_proof = validate_tree_proof(bundle, receipt["treeProof"])
    if tree_sha != tree_proof["candidateTreeSha"]:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_TREE_PROOF_MISMATCH")
    if branch_head != commit_sha:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_REF_COMMIT_MISMATCH")
    if parent_sha != bundle["baseHead"]:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_PARENT_MISMATCH")
    if receipt["changedPaths"] != bundle["expectedChangedPaths"]:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_CHANGED_PATHS_MISMATCH")
    content_hashes = receipt["contentSha256"]
    if not isinstance(content_hashes, dict):
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_CONTENT_INVALID")
    expected_hashes = {
        item["path"]: item["contentSha256"]
        for item in bundle["entries"]
        if item["operation"] == "write"
    }
    if content_hashes != expected_hashes:
        raise RuntimeError("GIT_MUTATION_BUNDLE_READBACK_CONTENT_MISMATCH")
    core = {
        "schemaVersion": READBACK_SCHEMA,
        "bundleHash": bundle["bundleHash"],
        "branch": bundle["branch"],
        "branchHead": branch_head,
        "commitSha": commit_sha,
        "parentSha": parent_sha,
        "treeSha": tree_sha,
        "treeProofHash": tree_proof["proofHash"],
        "changedPaths": bundle["expectedChangedPaths"],
        "contentSha256": expected_hashes,
        "status": "PASS",
    }
    return {**core, "readbackHash": stable_hash(core)}


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="git-mutation-bundle")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--repository", required=True)
    build.add_argument("--branch", required=True)
    build.add_argument("--base-head", required=True)
    build.add_argument("--base-tree", required=True)
    build.add_argument("--manifest", required=True)
    build.add_argument("--current-branch-head")
    build.add_argument("--json", action="store_true", dest="as_json")

    validate = sub.add_parser("validate")
    validate.add_argument("bundle")
    validate.add_argument("--json", action="store_true", dest="as_json")

    verify_tree_cmd = sub.add_parser("verify-tree")
    verify_tree_cmd.add_argument("bundle")
    verify_tree_cmd.add_argument("--base-tree-entries", required=True)
    verify_tree_cmd.add_argument("--candidate-tree-entries", required=True)
    verify_tree_cmd.add_argument("--candidate-tree-sha", required=True)
    verify_tree_cmd.add_argument("--json", action="store_true", dest="as_json")

    verify_readback_cmd = sub.add_parser("verify-readback")
    verify_readback_cmd.add_argument("bundle")
    verify_readback_cmd.add_argument("--receipt", required=True)
    verify_readback_cmd.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            manifest = _read_json(args.manifest)
            payload = build_bundle(
                repository=args.repository,
                branch=args.branch,
                base_head=args.base_head,
                base_tree_sha=args.base_tree,
                changes=manifest,
                current_branch_head=args.current_branch_head,
            )
        elif args.command == "validate":
            payload = validate_bundle(_read_json(args.bundle))
        elif args.command == "verify-tree":
            payload = verify_tree(
                validate_bundle(_read_json(args.bundle)),
                base_tree_entries=_read_json(args.base_tree_entries),
                candidate_tree_entries=_read_json(args.candidate_tree_entries),
                candidate_tree_sha=args.candidate_tree_sha,
            )
        else:
            payload = verify_readback(
                validate_bundle(_read_json(args.bundle)), _read_json(args.receipt)
            )
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("PASS")
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
