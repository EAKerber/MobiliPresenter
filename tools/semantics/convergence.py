from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from tools import prune_plan
from tools.canonical import stable_hash
from tools.semantics.registry import ROOT, load_registry, validate_registry

SCHEMA_VERSION = "ConvergenceInspection 0.2"
ALIAS_TARGETS = (
    ("coordination.lease", "lock", "cli-name"),
    ("branch.domain.operations", "ops", "legacy-branch-namespace"),
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt"}
CURRENT_ROLE_DIR = ROOT / "docs" / "kickstarts" / "roles"
MUTABLE_DIRECTION_RE = re.compile(
    r"\bcheckpoint\b|\bnextTransition\b|\bnext declared transition\b",
    re.IGNORECASE,
)
LOCK_CLI_RE = re.compile(r"(?:python(?:3)?\s+)?tools/lock\.py\b|python\s+-m\s+tools\.lock\b")
BRANCH_INLINE_RE = re.compile(r"branches\s*:\s*\[([^\]]*)\]")
QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")
TRIGGER_RETIREMENT_NAMESPACES = {"architecture", "ops", "renderer"}

CONSUMER_CLASSES = (
    "repository-tracked-files",
    "workflow-branch-triggers",
    "current-role-pointers",
    "operational-semantics-aliases",
    "live-branch-inventory",
    "open-pr-branch-relations",
    "work-authority-branch-relations",
)


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"AGENTS.md", "README.md"}:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def tracked_snapshot(*, root: Path = ROOT) -> tuple[list[dict[str, str]], dict[str, str]]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("CONVERGENCE_TRACKED_INVENTORY_UNAVAILABLE")
    names = sorted(
        item.decode("utf-8")
        for item in proc.stdout.split(b"\0")
        if item
    )
    records: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    for name in names:
        path = root / name
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"CONVERGENCE_TRACKED_FILE_UNREADABLE:{name}") from exc
        records.append({"path": name, "contentHash": _content_hash(data)})
        value = _text(path)
        if value is not None:
            texts[name] = value
    return records, texts


def _alias(
    registry: dict[str, Any], semantic_id: str, term: str, scope: str
) -> dict[str, Any] | None:
    concept = registry.get("concepts", {}).get(semantic_id)
    if not isinstance(concept, dict):
        raise RuntimeError(f"CONVERGENCE_SUBJECT_UNKNOWN:{semantic_id}")
    matches = [
        item for item in concept.get("aliases", [])
        if isinstance(item, dict) and item.get("term") == term and item.get("scope") == scope
    ]
    if len(matches) > 1:
        raise RuntimeError(f"CONVERGENCE_ALIAS_CARDINALITY_INVALID:{semantic_id}:{term}")
    return matches[0] if matches else None


def _consumer(kind: str, path: str, detail: str, *, blocking: bool = True) -> dict[str, Any]:
    return {"class": kind, "path": path, "detail": detail, "blocking": bool(blocking)}


def _sort_consumers(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str, bool], dict[str, Any]] = {}
    for item in values:
        key = (item["class"], item["path"], item["detail"], item["blocking"])
        unique[key] = item
    return [unique[key] for key in sorted(unique)]


def workflow_branch_patterns(text: str) -> list[str]:
    patterns: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        inline = BRANCH_INLINE_RE.search(line)
        if inline:
            patterns.extend(QUOTED_RE.findall(inline.group(1)))
            continue
        if not re.match(r"^\s*branches\s*:\s*$", line):
            continue
        indent = len(line) - len(line.lstrip())
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= indent:
                break
            item = re.match(r"^\s*-\s*['\"]?([^'\"\s]+)['\"]?\s*$", candidate)
            if item:
                patterns.append(item.group(1))
            cursor += 1
    return sorted(set(patterns))


def trigger_inventory(
    texts: dict[str, str],
    registry: dict[str, Any],
) -> list[dict[str, str]]:
    legacy = set(registry["branchGrammar"]["legacyNamespaces"])
    rows: list[dict[str, str]] = []
    for path, text in sorted(texts.items()):
        if not path.startswith(".github/workflows/"):
            continue
        for pattern in workflow_branch_patterns(text):
            prefix = pattern.split("/", 1)[0]
            if pattern in {"main", "work/**", "experiment/**"}:
                classification = "CANONICAL"
            elif prefix in legacy:
                classification = "LEGACY_NAMESPACE_TRIGGER"
            else:
                classification = "OTHER"
            rows.append({"path": path, "pattern": pattern, "classification": classification})
    return sorted(rows, key=lambda item: (item["path"], item["pattern"]))


def _branch_prefix(pattern: str) -> str | None:
    if pattern.endswith("/**"):
        return pattern[:-3] + "/"
    return None


def trigger_retirement_inventory(
    triggers: list[dict[str, str]],
    prune: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    entries = [item for item in prune.get("entries", []) if isinstance(item, dict)]
    open_heads = [item for item in prune.get("openPrHeads", []) if isinstance(item, str)]
    open_bases = [item for item in prune.get("openPrBases", []) if isinstance(item, str)]
    for trigger in triggers:
        if trigger["classification"] != "LEGACY_NAMESPACE_TRIGGER":
            continue
        namespace = trigger["pattern"].split("/", 1)[0]
        if namespace not in TRIGGER_RETIREMENT_NAMESPACES:
            continue
        prefix = _branch_prefix(trigger["pattern"])
        relations: list[str] = []
        if prefix is not None:
            for entry in entries:
                branch = entry.get("branch")
                if isinstance(branch, str) and branch.startswith(prefix):
                    relations.append(f"live-branch:{branch}")
                    if "active-work" in entry.get("protections", []):
                        relations.append(f"active-work:{branch}")
            relations.extend(f"open-pr-head:{branch}" for branch in open_heads if branch.startswith(prefix))
            relations.extend(f"open-pr-base:{branch}" for branch in open_bases if branch.startswith(prefix))
        relations = sorted(set(relations))
        rows.append({
            "path": trigger["path"],
            "pattern": trigger["pattern"],
            "classification": trigger["classification"],
            "retirementDisposition": "RETAIN" if relations else "RETIRE_READY",
            "blockingRelations": relations,
        })
    return sorted(rows, key=lambda item: (item["path"], item["pattern"]))


def current_pointer_residues(texts: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    prefix = "docs/kickstarts/roles/"
    for path, text in sorted(texts.items()):
        if not path.startswith(prefix) or not path.endswith("-current.md"):
            continue
        matches = sorted(set(match.group(0) for match in MUTABLE_DIRECTION_RE.finditer(text)))
        if matches:
            rows.append({
                "path": path,
                "kind": "CURRENT_POINTER_MUTABLE_DIRECTION",
                "detail": ",".join(matches),
            })
    return rows


def _current_role_contract_paths(texts: dict[str, str]) -> set[str]:
    paths: set[str] = set()
    prefix = "docs/kickstarts/roles/"
    target_re = re.compile(r"\]\(\./([A-Za-z0-9._-]+-v[A-Za-z0-9._-]+\.md)\)")
    for path, text in sorted(texts.items()):
        if not path.startswith(prefix) or not path.endswith("-current.md"):
            continue
        paths.add(path)
        targets = target_re.findall(text)
        if len(targets) == 1:
            paths.add(prefix + targets[0])
    return paths


def _python_imports_lock(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "tools.lock" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "tools.lock":
                return True
            if node.module == "tools" and any(alias.name == "lock" for alias in node.names):
                return True
    return False


def _lock_consumers(
    registry: dict[str, Any],
    texts: dict[str, str],
) -> list[dict[str, Any]]:
    consumers: list[dict[str, Any]] = []
    current_contracts = _current_role_contract_paths(texts)
    lock_text = texts.get("tools/lock.py")
    if lock_text is not None:
        if "LEGACY_LOCK_WRAPPER = True" in lock_text:
            consumers.append(_consumer(
                "LEGACY_COMPATIBILITY_WRAPPER",
                "tools/lock.py",
                "legacy CLI delegates to canonical Coordination surface",
            ))
        else:
            consumers.append(_consumer(
                "LEGACY_IMPLEMENTATION",
                "tools/lock.py",
                "legacy CLI implementation still exists",
            ))
    for component_id, item in registry.get("components", {}).items():
        if isinstance(item, dict) and item.get("module") == "tools.lock":
            consumers.append(_consumer(
                "REGISTERED_LEGACY_SURFACE",
                "ops/semantics/registry.json",
                f"component:{component_id}",
            ))
    self_paths = {"tools/semantics/convergence.py", "tools/tests/test_convergence_inspection.py"}
    for path, text in sorted(texts.items()):
        if path == "tools/lock.py" or path in self_paths:
            continue
        if path.endswith(".py"):
            if _python_imports_lock(text):
                kind = "COMPATIBILITY_TEST" if path.startswith("tools/tests/") else "ACTIVE_REPOSITORY_CONSUMER"
                consumers.append(_consumer(kind, path, "imports tools.lock"))
            continue
        if not LOCK_CLI_RE.search(text):
            continue
        if path in current_contracts or path == "AGENTS.md":
            consumers.append(_consumer("CURRENT_CONTRACT_REFERENCE", path, "invokes tools/lock.py"))
        elif path.startswith(".github/workflows/"):
            consumers.append(_consumer("ACTIVE_REPOSITORY_CONSUMER", path, "invokes tools/lock.py"))
        elif path.startswith("ops/evidence/"):
            consumers.append(_consumer("HISTORICAL_EVIDENCE_REFERENCE", path, "mentions tools/lock.py", blocking=False))
        elif path.startswith("docs/"):
            consumers.append(_consumer("DOCUMENTATION_REFERENCE", path, "mentions tools/lock.py", blocking=False))
        else:
            consumers.append(_consumer("REFERENCE_REQUIRES_REVIEW", path, "mentions tools/lock.py", blocking=True))
    return _sort_consumers(consumers)


def _ops_test_references(text: str) -> tuple[bool, bool]:
    """Return (has_legacy_reference, asserts_legacy_semantics) for one test module."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False, False
    has_reference = False
    semantic_assertion = False
    semantic_names = {
        "parse_branch_name",
        "semanticDomain",
        "legacyAlias",
        "aggregate_ci",
        "classification",
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        strings = {
            value.value
            for value in ast.walk(node)
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        }
        if not any(item.startswith("ops/") for item in strings):
            continue
        has_reference = True
        names = {
            value.id for value in ast.walk(node) if isinstance(value, ast.Name)
        } | {
            value.attr for value in ast.walk(node) if isinstance(value, ast.Attribute)
        }
        if names & semantic_names:
            semantic_assertion = True
    return has_reference, semantic_assertion


def _semantic_branch_runtime_consumer(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "tools.semantics.branches" and any(
                alias.name == "parse_branch_name" for alias in node.names
            ):
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name == "tools.semantics.branches" for alias in node.names):
                return True
    return False


def _ops_consumers(
    texts: dict[str, str],
    triggers: list[dict[str, str]],
    prune: dict[str, Any],
) -> list[dict[str, Any]]:
    consumers: list[dict[str, Any]] = []
    for row in triggers:
        if row["pattern"] == "ops/**":
            consumers.append(_consumer(
                "WORKFLOW_BRANCH_TRIGGER",
                row["path"],
                "push/listener branch pattern ops/**",
            ))
    for path, text in sorted(texts.items()):
        if path == "tools/tests/test_convergence_inspection.py":
            continue
        if path.startswith("tools/tests/"):
            has_reference, semantic_assertion = _ops_test_references(text)
            if semantic_assertion:
                consumers.append(_consumer(
                    "LEGACY_BRANCH_BEHAVIOR_ASSERTION",
                    path,
                    "test requires legacy ops branch semantics",
                ))
            elif has_reference:
                consumers.append(_consumer(
                    "LEGACY_BRANCH_REFERENCE",
                    path,
                    "legacy ops branch fixture/reference does not itself require alias semantics",
                    blocking=False,
                ))
            continue
        if path.endswith(".py") and _semantic_branch_runtime_consumer(text):
            consumers.append(_consumer(
                "SEMANTIC_BRANCH_CONSUMER",
                path,
                "consumes canonical branch parser; must remain valid after alias retirement",
                blocking=False,
            ))
    for entry in prune.get("entries", []):
        branch = entry.get("branch") if isinstance(entry, dict) else None
        if isinstance(branch, str) and branch.startswith("ops/"):
            consumers.append(_consumer("LIVE_BRANCH_CONSUMER", branch, "live branch inventory"))
            if "active-work" in entry.get("protections", []):
                consumers.append(_consumer("ACTIVE_WORK_BRANCH_CONSUMER", branch, "active Work relation"))
    for field in ("openPrHeads", "openPrBases"):
        for branch in prune.get(field, []):
            if isinstance(branch, str) and branch.startswith("ops/"):
                consumers.append(_consumer("OPEN_PR_BRANCH_CONSUMER", branch, field))
    return _sort_consumers(consumers)


def _subject(
    *,
    semantic_id: str,
    term: str,
    scope: str,
    alias: dict[str, Any] | None,
    consumers: list[dict[str, Any]],
    coverage_complete: bool,
) -> dict[str, Any]:
    alias_presence = "PRESENT" if alias is not None else "ABSENT"
    has_blocker = any(item["blocking"] for item in consumers)
    if not coverage_complete:
        readiness = "UNKNOWN"
    elif alias_presence == "ABSENT" and has_blocker:
        readiness = "INVALID"
    elif alias_presence == "ABSENT":
        readiness = "RETIRED"
    elif has_blocker:
        readiness = "MIGRATION_REQUIRED"
    else:
        readiness = "READY"
    return {
        "semanticId": semantic_id,
        "alias": {
            "term": term,
            "scope": scope,
            "status": alias.get("status") if alias else None,
            "retireBy": alias.get("retireBy") if alias else None,
        },
        "aliasPresence": alias_presence,
        "coverageStatus": "PASS" if coverage_complete else "UNKNOWN",
        "retirementReadiness": readiness,
        "consumers": consumers,
    }


def _coverage(prune: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    observations = prune.get("observations") if isinstance(prune, dict) else None
    flags = {
        "live-branch-inventory": bool(isinstance(observations, dict) and observations.get("branchInventoryComplete") is True),
        "open-pr-branch-relations": bool(isinstance(observations, dict) and observations.get("prHistoryComplete") is True),
        "work-authority-branch-relations": bool(isinstance(observations, dict) and observations.get("workAuthorityComplete") is True),
        "repository-tracked-files": True,
        "workflow-branch-triggers": True,
        "current-role-pointers": True,
        "operational-semantics-aliases": True,
    }
    rows = [
        {"class": name, "status": "PASS" if flags[name] else "UNKNOWN"}
        for name in CONSUMER_CLASSES
    ]
    return rows, all(flags.values())


def build_from_inputs(
    *,
    registry: dict[str, Any],
    tracked_records: list[dict[str, str]],
    texts: dict[str, str],
    prune: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(errors[0])
    prune_plan.validate_plan(prune, require_complete=False)
    coverage, complete = _coverage(prune)
    triggers = trigger_inventory(texts, registry)
    trigger_retirement = trigger_retirement_inventory(triggers, prune)
    residues = current_pointer_residues(texts)

    aliases = {
        (semantic_id, term, scope): _alias(registry, semantic_id, term, scope)
        for semantic_id, term, scope in ALIAS_TARGETS
    }
    subjects = [
        _subject(
            semantic_id="coordination.lease",
            term="lock",
            scope="cli-name",
            alias=aliases[("coordination.lease", "lock", "cli-name")],
            consumers=_lock_consumers(registry, texts),
            coverage_complete=complete,
        ),
        _subject(
            semantic_id="branch.domain.operations",
            term="ops",
            scope="legacy-branch-namespace",
            alias=aliases[("branch.domain.operations", "ops", "legacy-branch-namespace")],
            consumers=_ops_consumers(texts, triggers, prune),
            coverage_complete=complete,
        ),
    ]

    body = {
        "schemaVersion": SCHEMA_VERSION,
        "inputs": {
            "operationalSemanticsHash": stable_hash(registry),
            "trackedFilesHash": stable_hash(tracked_records),
            "gitPrunePlanHash": prune["planHash"],
        },
        "coverage": coverage,
        "subjects": subjects,
        "triggerInventory": triggers,
        "triggerRetirement": trigger_retirement,
        "residues": residues,
        "coverageComplete": complete,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "inspectionHash": stable_hash(body)}


def build_inspection(prune: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    records, texts = tracked_snapshot(root=root)
    return build_from_inputs(
        registry=load_registry(),
        tracked_records=records,
        texts=texts,
        prune=prune,
    )


def validate_inspection(value: Any) -> dict[str, Any]:
    required = {
        "schemaVersion", "inputs", "coverage", "subjects", "triggerInventory",
        "triggerRetirement", "residues", "coverageComplete", "readOnly",
        "semanticAuthority", "authorizesMutation", "inspectionHash",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("CONVERGENCE_INSPECTION_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("CONVERGENCE_INSPECTION_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True:
        raise RuntimeError("CONVERGENCE_INSPECTION_READ_ONLY_REQUIRED")
    if value.get("semanticAuthority") is not False:
        raise RuntimeError("CONVERGENCE_INSPECTION_SEMANTIC_AUTHORITY_FORBIDDEN")
    if value.get("authorizesMutation") is not False:
        raise RuntimeError("CONVERGENCE_INSPECTION_MUTATION_AUTHORITY_FORBIDDEN")
    coverage = value.get("coverage")
    if not isinstance(coverage, list) or [item.get("class") for item in coverage] != list(CONSUMER_CLASSES):
        raise RuntimeError("CONVERGENCE_INSPECTION_COVERAGE_INVALID")
    statuses = []
    for item in coverage:
        if not isinstance(item, dict) or set(item) != {"class", "status"} or item.get("status") not in {"PASS", "UNKNOWN"}:
            raise RuntimeError("CONVERGENCE_INSPECTION_COVERAGE_INVALID")
        statuses.append(item["status"])
    if value.get("coverageComplete") is not all(status == "PASS" for status in statuses):
        raise RuntimeError("CONVERGENCE_INSPECTION_COVERAGE_STATUS_MISMATCH")
    subjects = value.get("subjects")
    if not isinstance(subjects, list) or len(subjects) != len(ALIAS_TARGETS):
        raise RuntimeError("CONVERGENCE_INSPECTION_SUBJECTS_INVALID")
    for subject in subjects:
        if not isinstance(subject, dict) or set(subject) != {
            "semanticId", "alias", "aliasPresence", "coverageStatus",
            "retirementReadiness", "consumers"
        }:
            raise RuntimeError("CONVERGENCE_INSPECTION_SUBJECT_INVALID")
        if subject["aliasPresence"] not in {"PRESENT", "ABSENT"}:
            raise RuntimeError("CONVERGENCE_INSPECTION_ALIAS_PRESENCE_INVALID")
        if subject["coverageStatus"] not in {"PASS", "UNKNOWN"}:
            raise RuntimeError("CONVERGENCE_INSPECTION_SUBJECT_STATUS_INVALID")
        if subject["retirementReadiness"] not in {
            "READY", "MIGRATION_REQUIRED", "RETIRED", "INVALID", "UNKNOWN"
        }:
            raise RuntimeError("CONVERGENCE_INSPECTION_READINESS_INVALID")
        consumers = subject["consumers"]
        if not isinstance(consumers, list) or consumers != _sort_consumers(consumers):
            raise RuntimeError("CONVERGENCE_INSPECTION_CONSUMERS_NOT_NORMALIZED")
        blockers = any(item.get("blocking") is True for item in consumers)
        expected = (
            "UNKNOWN" if subject["coverageStatus"] == "UNKNOWN"
            else "INVALID" if subject["aliasPresence"] == "ABSENT" and blockers
            else "RETIRED" if subject["aliasPresence"] == "ABSENT"
            else "MIGRATION_REQUIRED" if blockers
            else "READY"
        )
        if subject["retirementReadiness"] != expected:
            raise RuntimeError("CONVERGENCE_INSPECTION_READINESS_MISMATCH")
    trigger_retirement = value.get("triggerRetirement")
    if not isinstance(trigger_retirement, list):
        raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_INVALID")
    for item in trigger_retirement:
        if not isinstance(item, dict) or set(item) != {
            "path", "pattern", "classification", "retirementDisposition", "blockingRelations"
        }:
            raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_INVALID")
        if item.get("classification") != "LEGACY_NAMESPACE_TRIGGER":
            raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_INVALID")
        if item.get("retirementDisposition") not in {"RETIRE_READY", "RETAIN"}:
            raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_INVALID")
        relations = item.get("blockingRelations")
        if not isinstance(relations, list) or relations != sorted(set(relations)):
            raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_INVALID")
        if (item["retirementDisposition"] == "RETAIN") is not bool(relations):
            raise RuntimeError("CONVERGENCE_INSPECTION_TRIGGER_RETIREMENT_MISMATCH")
    if not isinstance(value.get("residues"), list) or not isinstance(value.get("triggerInventory"), list):
        raise RuntimeError("CONVERGENCE_INSPECTION_COLLECTION_INVALID")
    core = {key: value[key] for key in value if key != "inspectionHash"}
    if stable_hash(core) != value.get("inspectionHash"):
        raise RuntimeError("CONVERGENCE_INSPECTION_HASH_MISMATCH")
    return value


def load_prune_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("CONVERGENCE_PRUNE_PLAN_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("CONVERGENCE_PRUNE_PLAN_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("CONVERGENCE_PRUNE_PLAN_INVALID")
    return value
