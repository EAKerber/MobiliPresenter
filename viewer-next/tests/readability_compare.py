from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE_PATH = Path(sys.argv[1])
CANDIDATE_PATH = Path(sys.argv[2])
OUTPUT_PATH = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-comparison.json")

# These are regression tolerances, not desired-quality thresholds. They allow tiny
# raster variation while preventing an unrelated visual edit from degrading a seam.
MAX_RECALL_DROP = 0.05
MAX_MEDIAN_CONTRAST_DROP = 0.015
MAX_P10_CONTRAST_DROP = 0.01
MAX_OFFSET_INCREASE_PX = 0.5


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    baseline_by_id = {probe["id"]: probe for probe in baseline["probes"]}
    candidate_by_id = {probe["id"]: probe for probe in candidate["probes"]}
    if baseline_by_id.keys() != candidate_by_id.keys():
        raise SystemExit("READABILITY_PROBE_SET_CHANGED")

    deltas = []
    regressions = []
    for probe_id in sorted(baseline_by_id):
        before = baseline_by_id[probe_id]
        after = candidate_by_id[probe_id]
        delta = {
            "id": probe_id,
            "edgeRecall": after["edgeRecall"] - before["edgeRecall"],
            "medianPeakContrast": after["medianPeakContrast"] - before["medianPeakContrast"],
            "p10PeakContrast": after["p10PeakContrast"] - before["p10PeakContrast"],
            "medianEdgeOffsetCanonicalPx": after["medianEdgeOffsetCanonicalPx"] - before["medianEdgeOffsetCanonicalPx"],
        }
        reasons = []
        if delta["edgeRecall"] < -MAX_RECALL_DROP:
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

    payload = {
        "schemaVersion": "ReadabilityComparison 1.0",
        "baseline": str(BASELINE_PATH),
        "candidate": str(CANDIDATE_PATH),
        "policy": {
            "maxRecallDrop": MAX_RECALL_DROP,
            "maxMedianContrastDrop": MAX_MEDIAN_CONTRAST_DROP,
            "maxP10ContrastDrop": MAX_P10_CONTRAST_DROP,
            "maxMedianOffsetIncreaseCanonicalPx": MAX_OFFSET_INCREASE_PX,
        },
        "pass": not regressions,
        "regressions": regressions,
        "deltas": deltas,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if regressions:
        raise SystemExit("READABILITY_REGRESSION")


if __name__ == "__main__":
    main()
