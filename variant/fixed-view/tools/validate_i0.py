from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "reference-assets"


class ValidationError(RuntimeError):
    pass


def load(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate() -> list[str]:
    modules_doc = load("modules.json")
    assembly = load("assembly.json")
    presets = load("presets.json")
    rules_doc = load("rules.json")
    references_doc = load("references.json")
    ui = load("ui-state.json")

    modules = modules_doc["modules"]
    ids = [m["id"] for m in modules]
    catalog_numbers = [m["catalogNumber"] for m in modules]
    require(len(ids) == len(set(ids)), "module ids must be unique")
    require(len(catalog_numbers) == len(set(catalog_numbers)), "catalog numbers must be unique")
    require(catalog_numbers == [f"{n:02d}" for n in range(1, 9)], "catalog must preserve items 01–08")
    require(all(m["commercialSelectable"] and m["visualSelectable"] for m in modules), "every module must be visually and commercially selectable")
    require(all("price" not in m["detail"] for m in modules), "module detail must not contain price")
    require(all(m["carcassColor"]["value"] in ("white", None) for m in modules), "carcasses must remain white or not-applicable")

    module_ids = set(ids)
    require(set(assembly["moduleOrder"]) == module_ids, "assembly module order must reference the complete catalog")
    require(set(assembly["defaultEnabledModuleIds"]).issubset(module_ids), "default enabled modules must exist")
    policy = assembly["selectionPolicy"]
    require(policy["checkboxAffectsVisual"] is True, "checkbox must affect visual presence")
    require(policy["checkboxAffectsCommercial"] is True, "checkbox must affect commercial selection")
    require(policy["sceneRemainsVisibleInDetail"] is True, "scene must remain visible during detail")
    require(assembly["camera"]["mode"] == "fixed", "variant camera must be fixed")

    wall_values = {candidate["value"] for candidate in assembly["wallEnvelope"]["candidates"]}
    require({3550, 3573}.issubset(wall_values), "both unresolved wall candidates must be preserved")
    require(assembly["wallEnvelope"]["widthMm"] is None, "unresolved wall width must remain null")

    rule_ids = {rule["id"] for rule in rules_doc["rules"]}
    require("lighting-requires-refrigerator-side-panel" in rule_ids, "lighting dependency rule is required")
    lighting_rule = next(rule for rule in rules_doc["rules"] if rule["id"] == "lighting-requires-refrigerator-side-panel")
    require(lighting_rule["when"]["moduleEnabled"] == "lighting", "lighting rule source mismatch")
    require(lighting_rule["requires"]["moduleEnabled"] == "refrigerator-side-panel", "lighting must require item 04")
    require(lighting_rule["severity"] == "blocking", "lighting dependency must be blocking")
    require(lighting_rule["resolution"]["type"] == "offer-enable-module", "lighting rule must offer a valid transition")

    lighting = next(m for m in modules if m["id"] == "lighting")
    require("lighting-requires-refrigerator-side-panel" in lighting.get("requirements", []), "lighting module must reference dependency rule")

    require(presets["policies"]["priceInModuleDetail"] is False, "price must remain outside module detail")
    require(presets["policies"]["customerOverride"]["allowed"] is True, "customer override must be allowed")
    require(presets["policies"]["customerOverride"]["silentAutoCorrection"] is False, "override must not be silently corrected")

    detail = ui["states"]["module-detail"]
    require(detail["sceneRegion"] == "composition-visible-selected-highlight", "detail state must preserve and highlight the scene")
    back = next(t for t in ui["transitions"] if t["event"] == "back-to-list")
    require("scene" in back["preserve"], "back transition must preserve the scene")

    reference_ids = {ref["id"] for ref in references_doc["references"]}
    require(assembly["projectContext"]["referenceId"] in reference_ids, "project context must reference known evidence")
    for candidate in assembly["wallEnvelope"]["candidates"]:
        require(candidate["sourceId"] in reference_ids, f"unknown wall-envelope source: {candidate['sourceId']}")
    for module in modules:
        for candidate in module["measurementCandidates"]:
            require(candidate["sourceId"] in reference_ids, f"unknown measurement source: {candidate['sourceId']}")
    for observation in references_doc["measurementObservations"]:
        require(observation["sourceId"] in reference_ids, f"unknown observation source: {observation['sourceId']}")

    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["archivePolicy"] == "identity-first", "reference archive policy mismatch")
    manifest_ids = {asset["id"] for asset in manifest["assets"]}
    require({"plant-context-upload", "plant-kitchen-upload"}.issubset(manifest_ids), "plant identities must be registered")
    for asset in manifest["assets"]:
        require(asset["bytes"] > 0, f"invalid asset byte count: {asset['id']}")
        require(len(asset["sha256"]) == 64, f"invalid asset sha256: {asset['id']}")
        require(asset["binaryPath"] is None, f"binary path must remain null until the file is promoted: {asset['id']}")

    return [
        f"{len(modules)} modules validated",
        f"{len(rules_doc['rules'])} rules validated",
        f"{len(references_doc['references'])} references validated",
        f"{len(manifest['assets'])} reference identities verified",
    ]


def main() -> None:
    for line in validate():
        print(line)


if __name__ == "__main__":
    main()
