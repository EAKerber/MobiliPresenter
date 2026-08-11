from __future__ import annotations

import json
import sys
from pathlib import Path

REPORT_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mobilipresenter-readability-report.json")
OUTPUT_PATH = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-sink-readability-gate.json")

REQUIRED_IDS = [
    "sink/opening/front",
    "sink/opening/back",
    "sink/opening/left",
    "sink/opening/right",
]
MIN_EDGE_RECALL = 0.90
MIN_MEDIAN_CONTRAST = 0.04
MIN_P10_CONTRAST = 0.03
MAX_MEDIAN_OFFSET_CANONICAL_PX = 1.0


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    by_id = {probe["id"]: probe for probe in report.get("probes", [])}
    missing = [probe_id for probe_id in REQUIRED_IDS if probe_id not in by_id]
    if missing:
        raise SystemExit(f"SINK_READABILITY_PROBES_MISSING:{','.join(missing)}")

    results = []
    failures = []
    for probe_id in REQUIRED_IDS:
        probe = by_id[probe_id]
        reasons = []
        if float(probe["edgeRecall"]) < MIN_EDGE_RECALL:
            reasons.append("edge-recall")
        if float(probe["medianPeakContrast"]) < MIN_MEDIAN_CONTRAST:
            reasons.append("median-contrast")
        if float(probe["p10PeakContrast"]) < MIN_P10_CONTRAST:
            reasons.append("p10-contrast")
        if float(probe["medianEdgeOffsetCanonicalPx"]) > MAX_MEDIAN_OFFSET_CANONICAL_PX:
            reasons.append("edge-offset")
        entry = {
            "id": probe_id,
            "edgeRecall": probe["edgeRecall"],
            "medianPeakContrast": probe["medianPeakContrast"],
            "p10PeakContrast": probe["p10PeakContrast"],
            "medianEdgeOffsetCanonicalPx": probe["medianEdgeOffsetCanonicalPx"],
            "failureReasons": reasons,
        }
        results.append(entry)
        if reasons:
            failures.append({"id": probe_id, "reasons": reasons})

    payload = {
        "schemaVersion": "SinkStationReadabilityGate 1.0",
        "sourceReport": str(REPORT_PATH),
        "thresholds": {
            "minEdgeRecall": MIN_EDGE_RECALL,
            "minMedianPeakContrast": MIN_MEDIAN_CONTRAST,
            "minP10PeakContrast": MIN_P10_CONTRAST,
            "maxMedianEdgeOffsetCanonicalPx": MAX_MEDIAN_OFFSET_CANONICAL_PX,
        },
        "pass": not failures,
        "failures": failures,
        "probes": results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if failures:
        raise SystemExit("SINK_STATION_READABILITY_GATE_FAILED")


if __name__ == "__main__":
    main()

# CI checkpoint: S9 functional implementation is in parent 914e73c4.
