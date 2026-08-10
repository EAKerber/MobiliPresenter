from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE_PATH = Path(sys.argv[1])
CANDIDATE_PATH = Path(sys.argv[2])
OUTPUT_PATH = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-comparison.json")
MIGRATION_PATH = Path(sys.argv[4]) if len(sys.argv) > 4 else None

# Regression tolerances, not desired-quality thresholds. Continuous contrast/offset
# metrics remain authoritative near the edge-detection threshold so a tiny contrast
# change cannot create a false 1.0 -> 0.0 recall cliff.
MAX_RECALL_DROP = 0.05
MAX_MEDIAN_CONTRAST_DROP = 0.015
MAX_P10_CONTRAST_DROP = 0.01
MAX_OFFSET_INCREASE_PX = 0.5


def load_migration() -> dict | None:
    if MIGRATION_PATH is None:
        return None
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
    if migration.get("schemaVersion") != "ReadabilityProbeMigration 1.0":
        raise SystemExit("READABILITY_MIGRATION_SCHEMA_UNSUPPORTED")
    return migration


def validate_probe_sets(baseline_by_id: dict, candidate_by_id: dict, migration: dict | None) -> list[str]:
    baseline_ids = set(baseline_by_id)
    candidate_ids = set(candidate_by_id)
    if migration is None:
        if baseline_ids != candidate_ids:
            raise SystemExit("READABILITY_PROBE_SET_CHANGED")
        return sorted(baseline_ids)

    unchanged = set(migration.get("unchangedProbeIds", []))
    superseded = set(migration.get("supersededProbeIds", []))
    added = set(migration.get("addedProbeIds", []))
    if unchanged & superseded or unchanged & added or superseded & added:
        raise SystemExit("READABILITY_MIGRATION_SETS_OVERLAP")
    if baseline_ids != unchanged | superseded:
        raise SystemExit("READABILITY_MIGRATION_BASELINE_SET_MISMATCH")
    if candidate_ids != unchanged | added:
        raise SystemExit("READABILITY_MIGRATION_CANDIDATE_SET_MISMATCH")
    if superseded & candidate_ids:
        raise SystemExit("READABILITY_SUPERSEDED_PROBE_STILL_PRESENT")
    if not added <= candidate_ids:
        raise SystemExit("READABILITY_ADDED_PROBE_MISSING")
    return sorted(unchanged)


def recall_is_robust(before: dict) -> bool:
    threshold = float(before["contrastThreshold"])
    return (
        float(before["medianPeakContrast"]) >= threshold + MAX_MEDIAN_CONTRAST_DROP
        and float(before["p10PeakContrast"]) >= threshold + MAX_P10_CONTRAST_DROP
    )


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    baseline_by_id = {probe["id"]: probe for probe in baseline["probes"]}
    candidate_by_id = {probe["id"]: probe for probe in candidate["probes"]}
    migration = load_migration()
    comparable_ids = validate_probe_sets(baseline_by_id, candidate_by_id, migration)

    deltas = []
    regressions = []
    for probe_id in comparable_ids:
        before = baseline_by_id[probe_id]
        after = candidate_by_id[probe_id]
        robust_recall = recall_is_robust(before)
        delta = {
            "id": probe_id,
            "edgeRecall": after["edgeRecall"] - before["edgeRecall"],
            "medianPeakContrast": after["medianPeakContrast"] - before["medianPeakContrast"],
            "p10PeakContrast": after["p10PeakContrast"] - before["p10PeakContrast"],
            "medianEdgeOffsetCanonicalPx": after["medianEdgeOffsetCanonicalPx"] - before["medianEdgeOffsetCanonicalPx"],
            "recallRegressionEnforced": robust_recall,
        }
        reasons = []
        if robust_recall and delta["edgeRecall"] < -MAX_RECALL_DROP:
            reasons.append("edge-recall")
        if delta["medianPeakContrast"] < -MAX_MEDIAN_CONTRAST_DROP:
            reasons.append("median-contrast")
        if delta["p10PeakContrast"] < -MAX_P10_CONTRAST_DROP:
            reasons.append("p10-contrast")
        if delta["medianEdgeOffsetCanonicalPx"] > MAX_OFFSET_INCREASE_PX:
            reasons.append("edge-offset")
        delta["regressionReasons"] = reasons
        deltas.append(delta)
        if reasons:
            regressions.append({"id": probe_id, "reasons": reasons})

    added_ids = sorted(migration.get("addedProbeIds", [])) if migration else []
    superseded_ids = sorted(migration.get("supersededProbeIds", [])) if migration else []
    payload = {
        "schemaVersion": "ReadabilityComparison 1.2",
        "baseline": str(BASELINE_PATH),
        "candidate": str(CANDIDATE_PATH),
        "migration": str(MIGRATION_PATH) if MIGRATION_PATH else None,
        "policy": {
            "maxRecallDrop": MAX_RECALL_DROP,
            "maxMedianContrastDrop": MAX_MEDIAN_CONTRAST_DROP,
            "maxP10ContrastDrop": MAX_P10_CONTRAST_DROP,
            "maxMedianOffsetIncreaseCanonicalPx": MAX_OFFSET_INCREASE_PX,
            "recallRequiresBaselineMargin": {
                "medianContrastMargin": MAX_MEDIAN_CONTRAST_DROP,
                "p10ContrastMargin": MAX_P10_CONTRAST_DROP,
            },
            "nearThresholdRecallIsDiagnosticOnly": True,
            "probeSetChangeRequiresExplicitMigration": True,
        },
        "pass": not regressions,
        "regressions": regressions,
        "deltas": deltas,
        "comparableProbeIds": comparable_ids,
        "newProbeIds": added_ids,
        "supersededProbeIds": superseded_ids,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if regressions:
        raise SystemExit("READABILITY_REGRESSION")


if __name__ == "__main__":
    main()
