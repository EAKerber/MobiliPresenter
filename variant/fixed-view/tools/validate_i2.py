from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "prototype" / "i2-data"
PROTOTYPE = ROOT / "prototype"


class ValidationError(RuntimeError):
    pass


def load_json(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate() -> list[str]:
    modules = [load_json(f"module-{number:02d}.json")["module"] for number in range(1, 9)]
    assembly = load_json("assembly.json")
    rules = load_json("rules.json")["rules"]
    layout = load_json("layout.json")
    presets = load_json("presets.json")
    references = load_json("references.json")

    ids = [module["id"] for module in modules]
    require(len(ids) == len(set(ids)) == 8, "I2 must expose eight unique modules")
    require(set(ids) == set(assembly["moduleOrder"]), "assembly order must cover I2 catalog")
    require(assembly["wallEnvelope"]["widthMm"] == 3550, "operational wall width must be 3550 mm")
    require(assembly["constructionPolicy"]["nominalDepthMm"] == 600, "prototype depth must be 600 mm")
    require(assembly["constructionPolicy"]["boardThicknessMm"] == 18, "MDF thickness must be 18 mm")
    require(assembly["appliancePolicy"]["identity"] == "illustrative-not-model-specific", "appliances must remain illustrative")

    furniture = [module for module in modules if module["placementClass"] != "feature"]
    for module in furniture:
        dimensions = module["dimensionsMm"]
        require(dimensions and dimensions.get("depth") == 600, f"{module['id']} depth must be 600 mm")
        require(module["frontTopology"]["elements"], f"{module['id']} topology is missing")

    lower_sink = next(module for module in modules if module["id"] == "lower-sink")
    types = [element["type"] for element in lower_sink["frontTopology"]["elements"]]
    require(lower_sink["structuralFeatures"]["drawers"] == 4, "item 03 must preserve four drawers")
    require(lower_sink["structuralFeatures"]["doors"] == 2, "item 03 must preserve two doors")
    require(types.count("drawer") == 4 and types.count("door") == 2, "item 03 visual topology mismatch")

    upper_sink = next(module for module in modules if module["id"] == "upper-sink")
    require(upper_sink["structuralFeatures"]["flapDoors"] == 1, "item 06 flap door missing")
    require(upper_sink["structuralFeatures"]["niches"] == 1, "item 06 microwave niche missing")
    require(any(element["type"] == "niche" for element in upper_sink["frontTopology"]["elements"]), "item 06 niche topology missing")

    side_panel = next(module for module in modules if module["id"] == "refrigerator-side-panel")
    require(side_panel["dimensionsMm"]["height"] == 2400, "item 04 height mismatch")
    require(side_panel["dimensionsMm"]["thickness"] == 18, "item 04 thickness mismatch")
    require("lighting-support" in side_panel["capabilities"], "item 04 lighting capability missing")

    rule_by_id = {rule["id"]: rule for rule in rules}
    lighting = rule_by_id["lighting-requires-refrigerator-side-panel"]
    require(lighting["severity"] == "blocking", "lighting dependency must block review")
    require(lighting["requires"]["moduleEnabled"] == "refrigerator-side-panel", "lighting must require item 04")
    stove = rule_by_id["lower-stove-disabled-shows-freestanding-stove"]
    require(stove["when"]["moduleDisabled"] == "lower-stove", "stove fallback trigger mismatch")
    require(stove["activates"]["fallbackId"] == "freestanding-stove", "stove fallback target mismatch")

    fallbacks = {item["id"]: item for item in layout.get("fallbacks", [])}
    require(fallbacks["freestanding-stove"]["when"]["moduleDisabled"] == "lower-stove", "fallback placement trigger mismatch")
    require({item["moduleId"] for item in layout["placements"]} == set(ids), "layout must cover eight modules")

    require(presets["policies"]["carcassColor"]["value"] == "white", "carcasses must remain white")
    require(presets["policies"]["priceInModuleDetail"] is False, "price must remain outside detail")
    require(references["appliances"]["status"] == "illustrative", "reference appliance policy mismatch")

    required_files = [
        PROTOTYPE / "i2" / "data-loader.js",
        PROTOTYPE / "i2" / "renderer.js",
        PROTOTYPE / "i2" / "app.js",
        PROTOTYPE / "app.js",
    ]
    for path in required_files:
        require(path.is_file() and path.stat().st_size > 0, f"missing runtime file: {path.relative_to(ROOT)}")

    renderer = (PROTOTYPE / "i2" / "renderer.js").read_text(encoding="utf-8")
    app = (PROTOTYPE / "i2" / "app.js").read_text(encoding="utf-8")
    require("frontTopology" in renderer, "topology-driven renderer missing")
    require("freestanding-stove" in renderer, "freestanding stove fallback renderer missing")
    require("mobilipresenter.fixed-view.i2" in app, "I2 isolated local state missing")

    return [
        "8 modules validated",
        f"{len(rules)} rules validated",
        "3550 mm operational wall validated",
        "600 mm prototype depth validated",
        "18 mm MDF policy validated",
        "item 03 topology: 4 drawers + 2 doors validated",
        "item 02 freestanding stove fallback validated",
        "I2 topology-driven runtime validated",
    ]


def main() -> None:
    for line in validate():
        print(line)


if __name__ == "__main__":
    main()
