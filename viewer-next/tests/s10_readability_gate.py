from __future__ import annotations

import json
import sys
from pathlib import Path

REPORT_PATH = Path(sys.argv[1])
OUTPUT_PATH = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-s10-readability-gate.json")

OVEN_IDS = (
    "module02/oven-opening-left",
    "module02/oven-opening-right",
    "module02/oven-opening-bottom",
    "module02/oven-opening-top",
)
DRAWER_IDS = (
    "module03/drawer-seam/1-2",
    "module03/drawer-seam/2-3",
    "module03/drawer-seam/3-4",
)

OVEN_POLICY = {
    "minEdgeRecall": 0.90,
    "minMedianPeakContrast": 0.12,
    "minP10PeakContrast": 0.10,
    "maxMedianEdgeOffsetCanonicalPx": 1.0,
    "maxP95EdgeOffsetCanonicalPx": 1.25,
}
DRAWER_POLICY = {
    "minEdgeRecall": 0.95,
    "minMedianPeakContrast": 0.12,
    "minP10PeakContrast": 0.10,
    "maxMedianEdgeOffsetCanonicalPx": 0.75,
    "maxMedianContrastSpread": 0.02,
}


def reasons_for_probe(probe: dict, policy: dict, include_p95: bool) -> list[str]:
    reasons: list[str] = []
    if float(probe["edgeRecall"]) < policy["minEdgeRecall"]:
        reasons.append("edge-recall")
    if float(probe["medianPeakContrast"]) < policy["minMedianPeakContrast"]:
        reasons.append("median-contrast")
    if float(probe["p10PeakContrast"]) < policy["minP10PeakContrast"]:
        reasons.append("p10-contrast")
    if float(probe["medianEdgeOffsetCanonicalPx"]) > policy["maxMedianEdgeOffsetCanonicalPx"]:
        reasons.append("median-edge-offset")
    if include_p95 and float(probe["p95EdgeOffsetCanonicalPx"]) > policy["maxP95EdgeOffsetCanonicalPx"]:
        reasons.append("p95-edge-offset")
    return reasons


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    by_id = {probe["id"]: probe for probe in report["probes"]}
    required = set(OVEN_IDS) | set(DRAWER_IDS)
    missing = sorted(required - set(by_id))
    if missing:
        raise SystemExit(f"S10_READABILITY_PROBES_MISSING:{','.join(missing)}")

    failures: list[dict] = []
    oven_results = []
    for probe_id in OVEN_IDS:
        probe = by_id[probe_id]
        reasons = reasons_for_probe(probe, OVEN_POLICY, include_p95=True)
        oven_results.append({"id": probe_id, "pass": not reasons, "reasons": reasons, "metrics": probe})
        if reasons:
            failures.append({"id": probe_id, "gate": "oven-absolute", "reasons": reasons})

    drawer_results = []
    drawer_medians: list[float] = []
    for probe_id in DRAWER_IDS:
        probe = by_id[probe_id]
        reasons = reasons_for_probe(probe, DRAWER_POLICY, include_p95=False)
        drawer_results.append({"id": probe_id, "pass": not reasons, "reasons": reasons, "metrics": probe})
        drawer_medians.append(float(probe["medianPeakContrast"]))
        if reasons:
            failures.append({"id": probe_id, "gate": "drawer-absolute", "reasons": reasons})

    drawer_spread = max(drawer_medians) - min(drawer_medians)
    uniformity_pass = drawer_spread <= DRAWER_POLICY["maxMedianContrastSpread"]
    if not uniformity_pass:
        failures.append({
            "id": "module03/drawer-seam/uniformity",
            "gate": "drawer-uniformity",
            "reasons": ["median-contrast-spread"],
        })

    payload = {
        "schemaVersion": "S10ReadabilityGate 1.0",
        "report": str(REPORT_PATH),
        "pass": not failures,
        "policy": {
            "oven": OVEN_POLICY,
            "drawers": DRAWER_POLICY,
            "rationale": "S10 intentionally changes lower-cabinet material response. Oven and drawer metric endpoints remain fixed, but appearance quality is gated absolutely instead of preserving historical contrast values."
        },
        "oven": oven_results,
        "drawers": {
            "probes": drawer_results,
            "medianContrastSpread": drawer_spread,
            "uniformityPass": uniformity_pass,
        },
        "failures": failures,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if failures:
        raise SystemExit("S10_READABILITY_GATE_FAILED")


if __name__ == "__main__":
    main()

# CI checkpoint: S10 explicit appearance migration gates.
