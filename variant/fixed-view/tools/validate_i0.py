from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "reference-assets"


class ValidationError(RuntimeError):
    pass


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValidationError(message)


def validate() -> list[str]:
    modules = load("modules.json")["modules"]
    assembly = load("assembly.json")
    presets = load("presets.json")
    rules = load("rules.json")["rules"]
    references = load("references.json")
    ui = load("ui-state.json")

    ids = [module["id"] for module in modules]
    numbers = [module["catalogNumber"] for module in modules]
    require(len(ids) == len(set(ids)), "module ids must be unique")
    require(numbers == [f"{n:02d}" for n in range(1, 9)], "catalog must preserve items 01–08")
    require(all(module["commercialSelectable"] and module["visualSelectable"] for module in modules), "all modules must be selectable")
    require(all("price" not in module["detail"] for module in modules), "module detail must not contain price")
    require(all(module["carcassColor"]["value"] in ("white", None) for module in modules), "carcasses must remain white or not-applicable")

    module_ids = set(ids)
    require(set(assembly["moduleOrder"]) == module_ids, "module order must cover the catalog")
    require(set(assembly["defaultEnabledModuleIds"]).issubset(module_ids), "default modules must exist")
    policy = assembly["selectionPolicy"]
    require(policy["checkboxAffectsVisual"] is True, "checkbox must affect visual presence")
    require(policy["checkboxAffectsCommercial"] is True, "checkbox must affect commercial selection")
    require(policy["sceneRemainsVisibleInDetail"] is True, "scene must remain visible during detail")
    require(assembly["camera"]["mode"] == "fixed", "camera must be fixed")

    wall = assembly["wallEnvelope"]
    values = {candidate["value"] for candidate in wall["candidates"]}
    require({3550, 3573}.issubset(values), "wall readings must remain traceable")
    require(wall["widthMm"] == 3550, "wall width must be 3550 mm")
    require(wall["status"] == "accepted-for-planning", "wall width must be planning-grade")
    require(wall["acceptedDifferenceMm"] == 23, "accepted difference must be 23 mm")
    chosen = next(candidate for candidate in wall["candidates"] if candidate["value"] == 3550)
    retained = next(candidate for candidate in wall["candidates"] if candidate["value"] == 3573)
    require(chosen["status"] == "selected", "3550 mm must be selected")
    require(retained["status"] == "retained-for-traceability", "3573 mm must remain traceable")
    require(retained["differenceFromSelectedMm"] == 23, "derived difference must remain explicit")

    rule_ids = {rule["id"] for rule in rules}
    require("lighting-requires-refrigerator-side-panel" in rule_ids, "lighting dependency is required")
    lighting_rule = next(rule for rule in rules if rule["id"] == "lighting-requires-refrigerator-side-panel")
    require(lighting_rule["when"]["moduleEnabled"] == "lighting", "lighting rule source mismatch")
    require(lighting_rule["requires"]["moduleEnabled"] == "refrigerator-side-panel", "lighting must require item 04")
    require(lighting_rule["severity"] == "blocking", "lighting dependency must block finalization")
    require(lighting_rule["resolution"]["type"] == "offer-enable-module", "lighting rule must offer a valid transition")
    lighting = next(module for module in modules if module["id"] == "lighting")
    require("lighting-requires-refrigerator-side-panel" in lighting.get("requirements", []), "lighting module must reference its rule")

    require(presets["policies"]["priceInModuleDetail"] is False, "price must remain outside detail")
    require(presets["policies"]["customerOverride"]["allowed"] is True, "customer override must be allowed")
    require(presets["policies"]["customerOverride"]["silentAutoCorrection"] is False, "override must not be silently corrected")

    detail = ui["states"]["module-detail"]
    require(detail["sceneRegion"] == "composition-visible-selected-highlight", "detail must preserve the scene")
    back = next(item for item in ui["transitions"] if item["event"] == "back-to-list")
    require("scene" in back["preserve"], "back must preserve the scene")

    reference_ids = {reference["id"] for reference in references["references"]}
    require(assembly["projectContext"]["referenceId"] in reference_ids, "project context must reference evidence")
    for candidate in wall["candidates"]:
        require(candidate["sourceId"] in reference_ids, "wall source must exist")
    for module in modules:
        for candidate in module["measurementCandidates"]:
            require(candidate["sourceId"] in reference_ids, "module measurement source must exist")
    for observation in references["measurementObservations"]:
        require(observation["sourceId"] in reference_ids, "observation source must exist")

    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["archivePolicy"] == "identity-first", "reference archive policy mismatch")
    manifest_ids = {asset["id"] for asset in manifest["assets"]}
    require({"plant-context-upload", "plant-kitchen-upload"}.issubset(manifest_ids), "plant identities must be registered")
    for asset in manifest["assets"]:
        require(asset["bytes"] > 0, "invalid asset byte count")
        require(len(asset["sha256"]) == 64, "invalid asset sha256")
        require(asset["binaryPath"] is None, "binary path must remain null until promotion")

    return [
        f"{len(modules)} modules validated",
        f"{len(rules)} rules validated",
        f"{len(references['references'])} references validated",
        f"{len(manifest['assets'])} reference identities verified",
    ]


if __name__ == "__main__":
    for result in validate():
        print(result)
