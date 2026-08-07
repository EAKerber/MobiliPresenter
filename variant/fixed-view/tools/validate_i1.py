from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROTOTYPE = ROOT / "prototype"


class ValidationError(RuntimeError):
    pass


def load_json(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate() -> list[str]:
    modules_doc = load_json("modules.json")
    rules_doc = load_json("rules.json")
    assembly = load_json("assembly.json")
    presets = load_json("presets.json")
    layout = load_json("i1-layout.json")

    modules = modules_doc["modules"]
    ids = [module["id"] for module in modules]
    expected_ids = set(assembly["moduleOrder"])
    require(len(modules) == 8, "I1 must expose eight catalog modules")
    require(len(ids) == len(set(ids)), "module ids must be unique")
    require(set(ids) == expected_ids, "assembly order must cover the module catalog")
    require(assembly["wallEnvelope"]["widthMm"] == 3550, "operational wall width must be 3550 mm")
    require(assembly["wallEnvelope"]["status"] == "accepted-for-planning", "wall width status mismatch")

    placements = layout["placements"]
    placement_ids = [placement["moduleId"] for placement in placements]
    require(len(placements) == 8, "I1 must provide eight provisional placements")
    require(set(placement_ids) == expected_ids, "provisional placements must cover all modules")
    require(len(placement_ids) == len(set(placement_ids)), "placement ids must be unique")
    require(layout["status"] == "provisional-visual-layout", "layout must remain explicitly provisional")
    for placement in placements:
        rect = placement["sceneRect"]
        require(all(rect[key] > 0 for key in ("width", "height")), f"invalid rectangle: {placement['moduleId']}")
        require(rect["x"] >= 0 and rect["y"] >= 0, f"negative placement: {placement['moduleId']}")

    rule_ids = {rule["id"] for rule in rules_doc["rules"]}
    require("lighting-requires-refrigerator-side-panel" in rule_ids, "lighting dependency is required")
    lighting_rule = next(rule for rule in rules_doc["rules"] if rule["id"] == "lighting-requires-refrigerator-side-panel")
    require(lighting_rule["severity"] == "blocking", "lighting dependency must block review")
    require(lighting_rule["requires"]["moduleEnabled"] == "refrigerator-side-panel", "lighting must require item 04")
    require(lighting_rule["resolution"]["type"] == "offer-enable-module", "lighting dependency must offer correction")

    require(presets["policies"]["carcassColor"]["value"] == "white", "carcasses must remain white")
    require(presets["policies"]["customerOverride"]["allowed"] is True, "customer override must remain allowed")
    require(presets["policies"]["priceInModuleDetail"] is False, "price must remain outside module detail")

    required_files = {
        "index.html",
        "styles.css",
        "runtime-data.js",
        "assets.js",
        "app.js",
    }
    for name in required_files:
        path = PROTOTYPE / name
        require(path.is_file() and path.stat().st_size > 0, f"missing prototype file: {name}")

    index = (PROTOTYPE / "index.html").read_text(encoding="utf-8")
    app = (PROTOTYPE / "app.js").read_text(encoding="utf-8")
    styles = (PROTOTYPE / "styles.css").read_text(encoding="utf-8")
    require('id="module-list"' in index, "checklist region is missing")
    require('id="catalog-detail-view"' in index, "detail region is missing")
    require('id="module-scene"' in index, "persistent scene is missing")
    require("sceneRemainsVisible" not in app or "selectModule" in app, "detail interaction contract missing")
    require("lighting-requires-refrigerator-side-panel" in app, "blocking dependency is not represented in runtime")
    require("localStorage" in app, "prototype state must persist locally")
    require("@media (max-width: 760px)" in styles, "mobile layout gate is missing")

    return [
        f"{len(modules)} modules validated",
        f"{len(rules_doc['rules'])} rules validated",
        f"{len(placements)} provisional placements validated",
        "3550 mm operational wall validated",
        f"{len(required_files)} prototype files validated",
    ]


def main() -> None:
    for line in validate():
        print(line)


if __name__ == "__main__":
    main()
