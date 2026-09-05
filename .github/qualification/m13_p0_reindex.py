from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from tools import cold_archive_plan as cold
from tools.canonical import canonical_json, stable_hash

REPO = "EAKerber/MobiliPresenter"
ARCHIVE_BRANCH = "archive/cold"
INDEX_PATH = "COLD_ARCHIVE.json"


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"GIT_FAIL:{' '.join(args)}:{(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def load_archive_index(commit: str) -> dict | None:
    raw = git("show", f"{commit}:{INDEX_PATH}", check=False)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ARCHIVE_INDEX_JSON_INVALID:{commit}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"ARCHIVE_INDEX_ROOT_INVALID:{commit}")
    if value.get("schemaVersion") not in {
        cold.LEGACY_INDEX_SCHEMA_VERSION,
        cold.INDEX_SCHEMA_VERSION,
    }:
        return None
    if value.get("repository") != REPO or value.get("archiveBranch") != ARCHIVE_BRANCH:
        return None
    return value


def main() -> int:
    archive_head = git("rev-parse", "origin/archive/cold")
    control_sha = git("rev-parse", "origin/main")
    current = archive_head
    observed_commits: list[str] = []
    recovered: dict[tuple[str, str], dict[str, str]] = {}
    superseded_metadata: list[dict] = []

    # Walk newest -> oldest. The first occurrence of an immutable identity wins.
    # Older metadata variants remain recoverable in Git and are recorded as
    # superseded migration evidence rather than silently reinterpreted.
    while True:
        index = load_archive_index(current)
        if index is None:
            break
        entries = index.get("entries")
        if not isinstance(entries, list) or not entries:
            raise SystemExit(f"ARCHIVE_INDEX_ENTRIES_INVALID:{current}")
        observed_commits.append(current)
        normalized = cold._normalize_entries(
            entries,
            control_branch="main",
            archive_branch=ARCHIVE_BRANCH,
            allow_empty=False,
            code="COLD_ARCHIVE_MIGRATION_ENTRIES",
        )
        for item in normalized:
            key = (item["branch"], item["headSha"])
            newer = recovered.get(key)
            if newer is None:
                recovered[key] = item
            elif newer != item:
                superseded_metadata.append(
                    {
                        "branch": item["branch"],
                        "headSha": item["headSha"],
                        "newest": newer,
                        "superseded": item,
                        "observedAtCommit": current,
                    }
                )

        first_parent = git("rev-parse", f"{current}^1", check=False)
        if not first_parent or load_archive_index(first_parent) is None:
            break
        current = first_parent

    entries = sorted(recovered.values(), key=lambda item: (item["branch"], item["headSha"]))
    if not entries:
        raise SystemExit("ARCHIVE_HISTORY_EMPTY")

    invalid_final_classifications = [
        item for item in entries
        if item["classification"] not in {
            "DUPLICATE_HISTORY",
            "ARTIFACT_HISTORY",
            "HISTORICAL_EVIDENCE",
            "PROMOTE_KNOWLEDGE_THEN_HISTORICAL",
            "CURRENT_KNOWLEDGE_ALREADY_PROMOTED",
        }
    ]
    if invalid_final_classifications:
        raise SystemExit(
            "ARCHIVE_FINAL_CLASSIFICATION_NOT_DELETE_EVIDENCE:"
            + ",".join(
                f"{x['branch']}@{x['headSha']}:{x['classification']}"
                for x in invalid_final_classifications
            )
        )

    unreachable: list[dict[str, str]] = []
    for item in entries:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", item["headSha"], archive_head],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            unreachable.append(item)
    if unreachable:
        raise SystemExit(
            "ARCHIVE_HISTORY_UNREACHABLE:"
            + ",".join(f"{x['branch']}@{x['headSha']}" for x in unreachable)
        )

    seed = {
        "schemaVersion": cold.INDEX_SCHEMA_VERSION,
        "repository": REPO,
        "archiveBranch": ARCHIVE_BRANCH,
        "controlSha": control_sha,
        "entries": entries,
    }
    Path("/tmp/cold-archive-cumulative-seed.json").write_text(
        canonical_json(seed) + "\n", encoding="utf-8"
    )

    plan = cold.build_plan(
        control_sha=control_sha,
        previous_archive_head=archive_head,
        existing_entries=entries,
        sources=[],
        operation="reindex",
    )
    cold.validate_plan(plan)
    index_content = cold.render_index(plan)
    Path("/tmp/cold-archive-reindex-plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path("/tmp/COLD_ARCHIVE.json").write_text(index_content, encoding="utf-8")

    evidence = {
        "schemaVersion": "ColdArchiveIndexMigrationEvidence 0.2",
        "repository": REPO,
        "archiveHead": archive_head,
        "controlSha": control_sha,
        "archiveCommitsObserved": observed_commits,
        "archiveIndexCount": len(observed_commits),
        "recoveredEntryCount": len(entries),
        "entrySetHash": stable_hash(entries),
        "supersededMetadataCount": len(superseded_metadata),
        "supersededMetadata": superseded_metadata,
        "unreachableCount": len(unreachable),
        "invalidFinalClassificationCount": len(invalid_final_classifications),
        "reindexPlanHash": plan["planHash"],
        "renderedIndexSha256": hashlib.sha256(index_content.encode("utf-8")).hexdigest(),
        "status": "PASS",
    }
    Path("/tmp/cold-archive-migration-evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
