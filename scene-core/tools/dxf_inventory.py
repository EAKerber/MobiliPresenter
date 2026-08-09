from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {"LINE", "3DFACE"}


@dataclass(frozen=True)
class Entity:
    kind: str
    layer: str
    points: tuple[tuple[float, float, float], ...]


def _pairs(text: str):
    lines = text.splitlines()
    if len(lines) % 2:
        raise ValueError("DXF_ODD_GROUP_LINES")
    for i in range(0, len(lines), 2):
        try:
            code = int(lines[i].strip())
        except ValueError as exc:
            raise ValueError(f"DXF_GROUP_CODE_INVALID:{i + 1}") from exc
        yield code, lines[i + 1].strip()


def parse_entities(path: Path) -> list[Entity]:
    pairs = list(_pairs(path.read_text(encoding="latin-1")))
    entities: list[Entity] = []
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code != 0 or value not in SUPPORTED:
            i += 1
            continue
        kind = value
        j = i + 1
        data: dict[int, list[str]] = {}
        while j < len(pairs) and pairs[j][0] != 0:
            data.setdefault(pairs[j][0], []).append(pairs[j][1])
            j += 1
        layer = (data.get(8) or ["0"])[0]
        indices = [0, 1] if kind == "LINE" else [0, 1, 2, 3]
        points = []
        for index in indices:
            xcode, ycode, zcode = 10 + index, 20 + index, 30 + index
            if xcode not in data or ycode not in data:
                raise ValueError(f"DXF_VERTEX_MISSING:{kind}:{layer}:{index}")
            points.append((
                float(data[xcode][0]),
                float(data[ycode][0]),
                float((data.get(zcode) or ["0"])[0]),
            ))
        entities.append(Entity(kind, layer, tuple(points)))
        i = j
    return entities


def inventory(path: Path) -> dict:
    raw = path.read_bytes()
    entities = parse_entities(path)
    layers: dict[str, dict] = {}
    for entity in entities:
        item = layers.setdefault(entity.layer, {
            "count": 0,
            "entityTypes": set(),
            "min": [math.inf] * 3,
            "max": [-math.inf] * 3,
        })
        item["count"] += 1
        item["entityTypes"].add(entity.kind)
        for point in entity.points:
            for axis in range(3):
                item["min"][axis] = min(item["min"][axis], point[axis])
                item["max"][axis] = max(item["max"][axis], point[axis])

    normalized = {}
    for layer in sorted(layers):
        item = layers[layer]
        normalized[layer] = {
            "count": item["count"],
            "entityTypes": sorted(item["entityTypes"]),
            "min": [round(value, 6) for value in item["min"]],
            "max": [round(value, 6) for value in item["max"]],
            "size": [round(item["max"][axis] - item["min"][axis], 6) for axis in range(3)],
        }
    return {
        "schemaVersion": "DxfInventory 0.1.0",
        "source": {
            "name": path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "entityCount": len(entities),
        "layers": normalized,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic R12 LINE/3DFACE inventory")
    parser.add_argument("dxf", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = inventory(args.dxf)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['source']['name']} entities={payload['entityCount']} "
            f"layers={len(payload['layers'])} sha256={payload['source']['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
