#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"REPLACE_COUNT:{path}:{count}:{old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


def insert_before(path: str, marker: str, block: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if block.strip() in text:
        return
    if text.count(marker) != 1:
        raise RuntimeError(f"MARKER_COUNT:{path}:{text.count(marker)}:{marker!r}")
    p.write_text(text.replace(marker, block + "\n\n" + marker), encoding="utf-8")


# continuation.py: canonical inventory envelope for authority-wide hashing/readback.
replace_once(
    "tools/continuation.py",
    'CANDIDATE_SCHEMA_VERSION = "ContinuationState 0.2"\nSCHEMA = CURRENT_SCHEMA_VERSION',
    'CANDIDATE_SCHEMA_VERSION = "ContinuationState 0.2"\nINVENTORY_SCHEMA_VERSION = "WorkAuthorityInventory 0.1"\nSCHEMA = CURRENT_SCHEMA_VERSION',
)
insert_before(
    "tools/continuation.py",
    "def load(cid: str) -> dict[str, Any]:",
    '''def inventory_state(items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(items, dict):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_INVALID")
    ordered: list[dict[str, Any]] = []
    for cid in sorted(items):
        if not ID_RE.fullmatch(str(cid)):
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ID_INVALID")
        value = items[cid]
        valid_compatible(value, cid)
        if value.get("id") != cid:
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ID_MISMATCH")
        ordered.append(copy.deepcopy(value))
    return {"schemaVersion": INVENTORY_SCHEMA_VERSION, "items": ordered}


def inventory_items(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "items"}:
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_FIELDS_INVALID")
    if value.get("schemaVersion") != INVENTORY_SCHEMA_VERSION or not isinstance(value.get("items"), list):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_SCHEMA_INVALID")
    out: dict[str, dict[str, Any]] = {}
    for item in value["items"]:
        if not isinstance(item, dict):
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ITEM_INVALID")
        cid = item.get("id")
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in out:
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ID_INVALID")
        valid_compatible(item, cid)
        out[cid] = copy.deepcopy(item)
    if list(out) != sorted(out):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_ORDER_INVALID")
    return out''',
)

# continuation_transition.py: one deterministic whole-authority migration plan.
insert_before(
    "tools/continuation_transition.py",
    "def validate_plan(\n",
    '''def validate_work_inventory(items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(items, dict):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_INVALID")
    views = [continuation.operational_view(items[cid]) for cid in sorted(items)]
    return work_graph.build(views)


def migrate_schema(items: dict[str, dict[str, Any]], authority_head: str) -> dict[str, Any]:
    if not isinstance(authority_head, str) or not re.fullmatch(r"[0-9a-f]{40}", authority_head):
        raise RuntimeError("WORK_AUTHORITY_HEAD_INVALID")
    before = continuation.inventory_state(items)
    candidate_items: dict[str, dict[str, Any]] = {}
    for cid, value in sorted(items.items()):
        continuation.valid(value, cid)
        if value["status"] != WorkStatus.DONE.value:
            raise RuntimeError("WORK_AUTHORITY_MIGRATION_REQUIRES_TERMINAL_INVENTORY")
        candidate_items[cid] = continuation.migrate_v01_to_v02(value)
    validate_work_inventory(candidate_items)
    candidate = continuation.inventory_state(candidate_items)
    return protocol.build_plan(
        domain="work",
        action="migrate-schema",
        subject={"kind": "authority", "id": "continuations"},
        authority=_authority(),
        before=before,
        candidate=candidate,
        intent={
            "authorityHead": authority_head,
            "fromSchemaVersion": continuation.CURRENT_SCHEMA_VERSION,
            "toSchemaVersion": continuation.CANDIDATE_SCHEMA_VERSION,
            "itemCount": len(candidate_items),
        },
        reversibility="revertible",
    )


def validate_migration_plan(
    plan: dict[str, Any],
    items: dict[str, dict[str, Any]],
    authority_head: str,
    *,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_dir: str = DEFAULT_DIR,
) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan.get("domain") != "work" or plan.get("action") != "migrate-schema":
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_PLAN_INVALID")
    if plan.get("subject") != {"kind": "authority", "id": "continuations"}:
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_SUBJECT_INVALID")
    if plan.get("authority") != _authority(repository, authority_branch, state_dir):
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_AUTHORITY_INVALID")
    intent = plan.get("intent")
    if not isinstance(intent, dict) or set(intent) != {"authorityHead", "fromSchemaVersion", "toSchemaVersion", "itemCount"}:
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_INTENT_INVALID")
    if intent.get("authorityHead") != authority_head:
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_HEAD_STALE")
    rebuilt = migrate_schema(items, authority_head)
    if rebuilt != plan:
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_PLAN_STALE")
    candidate_items = continuation.inventory_items(plan["candidate"])
    if any(item.get("schemaVersion") != continuation.CANDIDATE_SCHEMA_VERSION for item in candidate_items.values()):
        raise RuntimeError("WORK_AUTHORITY_MIGRATION_CANDIDATE_INVALID")
    validate_work_inventory(candidate_items)
    return plan''',
)

# continuation_remote.py: bridge reads both versions, ordinary writes remain V0.1-only,
# and migration publishes the complete inventory in one Git commit/CAS.
replace_once(
    "tools/continuation_remote.py",
    "        errors = continuation.validate_current(value, cid)\n",
    "        errors = continuation.validate_compatible(value, cid)\n",
)
insert_before(
    "tools/continuation_remote.py",
    "    def apply(self, planned: dict[str, Any], expected_plan: str | None) -> dict[str, Any]:",
    '''    def _commit_inventory(self, observed: Observation, items: dict[str, dict[str, Any]], message: str) -> str:
        tree_entries: list[dict[str, Any]] = []
        for cid in sorted(items):
            content = json.dumps(items[cid], indent=2, ensure_ascii=False) + "\\n"
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
            tree_entries.append({
                "path": f"{self.state_dir}/{cid}.json",
                "mode": "100644",
                "type": "blob",
                "sha": blob,
            })
        tree = self._sha(
            self._json(
                self.transport.request(
                    "POST",
                    f"repos/{self.repository}/git/trees",
                    payload={"base_tree": observed.tree_sha, "tree": tree_entries},
                ),
                "create tree",
            ).get("sha"),
            "tree",
        )
        commit = self._sha(
            self._json(
                self.transport.request(
                    "POST",
                    f"repos/{self.repository}/git/commits",
                    payload={"message": message, "tree": tree, "parents": [observed.head_sha]},
                ),
                "create commit",
            ).get("sha"),
            "commit",
        )
        try:
            self.transport.request("PATCH", self.update_endpoint, payload={"sha": commit, "force": False})
        except ApiError as exc:
            raise ContinuationRemoteError("CONTINUATION_CAS_LOST", exc.detail) from exc
        return commit

    def apply_migration(self, planned: dict[str, Any], expected_plan: str | None) -> dict[str, Any]:
        try:
            protocol.require_expected_plan(planned, expected_plan)
        except RuntimeError as exc:
            raise ContinuationRemoteError(str(exc).split(":", 1)[0]) from exc
        observed = self.observe()
        try:
            transition.validate_migration_plan(
                planned,
                observed.items,
                observed.head_sha,
                repository=self.repository,
                authority_branch=self.authority_branch,
                state_dir=self.state_dir,
            )
        except RuntimeError as exc:
            raise ContinuationRemoteError(str(exc).split(":", 1)[0]) from exc
        candidate_items = continuation.inventory_items(planned["candidate"])
        self._commit_inventory(observed, candidate_items, "work: migrate continuation authority to 0.2")
        last: Observation | None = None
        for attempt in range(self.readback_attempts):
            readback = self.observe()
            last = readback
            try:
                transition.validate_work_inventory(readback.items)
                state = continuation.inventory_state(readback.items)
                if protocol.state_hash(state) == planned["afterStateHash"]:
                    if any(value.get("schemaVersion") != continuation.CANDIDATE_SCHEMA_VERSION for value in readback.items.values()):
                        raise ContinuationRemoteError("WORK_AUTHORITY_MIGRATION_READBACK_SCHEMA_MISMATCH")
                    receipt = protocol.build_receipt(planned, state, authority_revision=readback.head_sha)
                    protocol.validate_receipt(receipt, planned)
                    return receipt
            except RuntimeError as exc:
                raise ContinuationRemoteError("WORK_AUTHORITY_MIGRATION_READBACK_INVALID", str(exc)) from exc
            if attempt + 1 < self.readback_attempts:
                time.sleep(self.readback_retry_seconds)
        if last is not None and last.head_sha == observed.head_sha:
            raise ContinuationRemoteError("CONTINUATION_READBACK_HEAD_STALE")
        raise ContinuationRemoteError("WORK_AUTHORITY_MIGRATION_READBACK_MISMATCH")''',
)
replace_once(
    "tools/continuation_remote.py",
    "        observed = self.observe()\n        current = observed.items.get(cid)\n",
    "        observed = self.observe()\n        if any(value.get(\"schemaVersion\") != continuation.CURRENT_SCHEMA_VERSION for value in observed.items.values()):\n            raise ContinuationRemoteError(\"CONTINUATION_MIGRATION_WINDOW_READ_ONLY\")\n        current = observed.items.get(cid)\n",
)

# continuation_live.py: expose plan/apply for the one authority migration and make
# read-only listing compatible with both schemas during the bridge window.
replace_once(
    "tools/continuation_live.py",
    "from tools import continuation\nfrom tools import continuation_transition as transition\n",
    "from tools import continuation, work_graph\nfrom tools import continuation_transition as transition\n",
)
replace_once(
    "tools/continuation_live.py",
    '    command = sub.add_parser("create")\n',
    '    command = sub.add_parser("migrate-schema")\n    flags(command)\n    command = sub.add_parser("create")\n',
)
insert_before(
    "tools/continuation_live.py",
    "def output(value, as_json: bool) -> None:",
    '''def work_summary(value: dict) -> dict:
    view = continuation.operational_view(value)
    return {
        "id": view["id"],
        "workerId": view["workerId"],
        "status": view["status"],
        "nextAction": view["nextAction"],
        "stateHash": continuation.state_hash(value),
        "sourceSchemaVersion": value["schemaVersion"],
    }''',
)
replace_once(
    "tools/continuation_live.py",
    "    try:\n        if args.command in {\"list\", \"verify\", \"show\"}:\n",
    '''    try:
        if args.command == "migrate-schema":
            observation = authority.observe()
            planned = transition.migrate_schema(observation.items, observation.head_sha)
            payload = authority.apply_migration(planned, args.expected_plan) if args.apply else planned
            output(payload, args.as_json)
            return 0
        if args.command in {"list", "verify", "show"}:
''',
)
replace_once(
    "tools/continuation_live.py",
    '''                    "schemaVersion": "ContinuationDiscovery 0.1",
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "items": [
                        {"id": value["id"], "actor": value["actor"], "status": value["status"], "nextAction": value["nextAction"], "stateHash": continuation.state_hash(value)}
                        for _, value in sorted(observation.items.items())
                    ],
''',
    '''                    "schemaVersion": "WorkDiscovery 0.1",
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "items": [work_summary(value) for _, value in sorted(observation.items.items())],
''',
)
replace_once(
    "tools/continuation_live.py",
    '''            elif args.command == "verify":
                payload = {
                    "ok": True,
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "count": len(observation.items),
                    "ids": sorted(observation.items),
                }
''',
    '''            elif args.command == "verify":
                graph = work_graph.build([continuation.operational_view(value) for _, value in sorted(observation.items.items())])
                payload = {
                    "ok": True,
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "count": len(observation.items),
                    "ids": sorted(observation.items),
                    "workGraph": graph,
                }
''',
)

# Focused M5B-A tests.
(ROOT / "tools/tests/test_m5b_work_authority_migration.py").write_text(r'''from __future__ import annotations

import unittest

from tools import continuation, continuation_transition as transition, transition_protocol as protocol
from tools.continuation_remote import GitHubContinuationAuthority, Observation


def terminal_v01(cid: str, actor: str = "worker-a") -> dict:
    return {
        "schemaVersion": continuation.CURRENT_SCHEMA_VERSION,
        "id": cid,
        "actor": actor,
        "status": "DONE",
        "branch": None,
        "prNumber": None,
        "completed": ["done"],
        "remaining": [],
        "nextAction": None,
        "lastKnownGood": {"sha": None, "checkpoint": "done"},
        "blockedBy": [],
        "handoffTo": None,
    }


class FakeMigrationAuthority(GitHubContinuationAuthority):
    def __init__(self, before: dict[str, dict], after: dict[str, dict], head: str):
        super().__init__(transport=object(), readback_attempts=1, readback_retry_seconds=0)
        self.before = before
        self.after = after
        self.head = head
        self.calls = 0
        self.published = None

    def observe(self):
        self.calls += 1
        if self.calls == 1:
            return Observation(self.head, "1" * 40, self.before)
        return Observation("2" * 40, "3" * 40, self.after)

    def _commit_inventory(self, observed, items, message):
        self.published = (observed, items, message)
        return "2" * 40


class WorkAuthorityMigrationTests(unittest.TestCase):
    def test_migration_is_deterministic_and_sorted(self):
        items = {"work-b": terminal_v01("work-b", "worker-b"), "work-a": terminal_v01("work-a")}
        head = "a" * 40
        plan1 = transition.migrate_schema(items, head)
        plan2 = transition.migrate_schema(dict(reversed(list(items.items()))), head)
        self.assertEqual(plan1, plan2)
        self.assertEqual([item["id"] for item in plan1["candidate"]["items"]], ["work-a", "work-b"])
        self.assertTrue(all(item["schemaVersion"] == continuation.CANDIDATE_SCHEMA_VERSION for item in plan1["candidate"]["items"]))
        transition.validate_migration_plan(plan1, items, head)

    def test_migration_refuses_active_inventory(self):
        item = terminal_v01("work-a")
        item.update(status="READY", remaining=["x"], nextAction="do x", completed=[])
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_MIGRATION_REQUIRES_TERMINAL_INVENTORY"):
            transition.migrate_schema({"work-a": item}, "a" * 40)

    def test_migration_plan_is_bound_to_authority_head(self):
        items = {"work-a": terminal_v01("work-a")}
        plan = transition.migrate_schema(items, "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_MIGRATION_HEAD_STALE"):
            transition.validate_migration_plan(plan, items, "b" * 40)

    def test_apply_migration_publishes_inventory_once_and_verifies_receipt(self):
        before = {"work-a": terminal_v01("work-a"), "work-b": terminal_v01("work-b", "worker-b")}
        head = "a" * 40
        plan = transition.migrate_schema(before, head)
        after = continuation.inventory_items(plan["candidate"])
        authority = FakeMigrationAuthority(before, after, head)
        receipt = authority.apply_migration(plan, plan["planHash"])
        self.assertIsNotNone(authority.published)
        self.assertEqual(authority.published[1], after)
        self.assertEqual(authority.calls, 2)
        protocol.validate_receipt(receipt, plan)
        self.assertEqual(receipt["authorityRevision"], "2" * 40)

    def test_inventory_envelope_rejects_noncanonical_order(self):
        value = {
            "schemaVersion": continuation.INVENTORY_SCHEMA_VERSION,
            "items": [terminal_v01("work-b"), terminal_v01("work-a")],
        }
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_INVENTORY_ORDER_INVALID"):
            continuation.inventory_items(value)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("M5B-A candidate transformations materialized")
