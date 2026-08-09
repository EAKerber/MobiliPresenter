from __future__ import annotations

import argparse
import json
from pathlib import Path

from dxf_inventory import inventory


def _close(a: float, b: float, tolerance: float = 0.05) -> bool:
    return abs(a - b) <= tolerance


def validate(profile_path: Path, placement_path: Path, surface_path: Path) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    placement = inventory(placement_path)
    surface = inventory(surface_path)
    checks = []

    for key, observed in (("placementLines", placement), ("surfaceFaces", surface)):
        expected = profile["sources"][key]
        ok = (
            observed["source"]["sha256"] == expected["sha256"]
            and observed["source"]["bytes"] == expected["bytes"]
            and len(observed["layers"]) == expected["usedLayers"]
        )
        checks.append({
            "name": f"source:{key}",
            "ok": ok,
            "code": None if ok else "SOURCE_MISMATCH",
        })

    translation = profile["sources"]["surfaceFaces"]["toAbsoluteTranslationMm"]
    for evidence in profile["translationEvidence"]:
        placement_layer = placement["layers"].get(evidence["placementLayer"])
        surface_layer = surface["layers"].get(evidence["surfaceLayer"])
        if not placement_layer or not surface_layer:
            checks.append({
                "name": f"anchor:{evidence['role']}",
                "ok": False,
                "code": "ANCHOR_LAYER_MISSING",
            })
            continue

        size_ok = all(
            _close(line_size, expected_size) and _close(face_size, expected_size)
            for line_size, expected_size, face_size in zip(
                placement_layer["size"], evidence["sizeMm"], surface_layer["size"]
            )
        )
        observed_translation = [
            round(placement_layer["min"][axis] - surface_layer["min"][axis], 6)
            for axis in range(3)
        ]
        translation_ok = all(
            _close(observed_translation[axis], translation[axis]) for axis in range(3)
        )
        checks.append({
            "name": f"anchor:{evidence['role']}",
            "ok": size_ok and translation_ok,
            "code": None if size_ok and translation_ok else "ANCHOR_MISMATCH",
            "observedTranslationMm": observed_translation,
        })

    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paired Promob DXF source profile")
    parser.add_argument("profile", type=Path)
    parser.add_argument("placement", type=Path)
    parser.add_argument("surface", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(args.profile, args.placement, args.surface)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for check in result["checks"]:
            print("PASS" if check["ok"] else "FAIL", check["name"], check.get("code") or "")
        print("PASS" if result["ok"] else "BLOCKED")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
