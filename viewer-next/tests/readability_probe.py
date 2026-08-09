from __future__ import annotations

import json
import math
import statistics
import struct
import sys
import zlib
from pathlib import Path

PNG = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mobilipresenter-fidelity-clean-4x.png")
SPEC = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-readability-spec.json")
OUTPUT = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-report.json")
SAMPLES_PER_PROBE = 48


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def parse_png(path: Path, needed_rows: set[int]) -> tuple[int, int, int, dict[int, bytes]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("READABILITY_NOT_PNG")
    offset = 8
    idat = bytearray()
    width = height = bit_depth = color_type = interlace = None
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise RuntimeError("READABILITY_PNG_IHDR_MISSING")
    if bit_depth != 8 or interlace != 0 or color_type not in {2, 6}:
        raise RuntimeError(f"READABILITY_PNG_UNSUPPORTED:{bit_depth}:{color_type}:{interlace}")
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise RuntimeError(f"READABILITY_PNG_SIZE_MISMATCH:{len(raw)}:{expected}")

    rows: dict[int, bytes] = {}
    prior = bytearray(stride)
    cursor = 0
    for y in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = raw[cursor:cursor+stride]
        cursor += stride
        row = bytearray(stride)
        for i, value in enumerate(encoded):
            left = row[i-channels] if i >= channels else 0
            up = prior[i]
            up_left = prior[i-channels] if i >= channels else 0
            if filter_type == 0:
                decoded = value
            elif filter_type == 1:
                decoded = (value + left) & 255
            elif filter_type == 2:
                decoded = (value + up) & 255
            elif filter_type == 3:
                decoded = (value + ((left + up) // 2)) & 255
            elif filter_type == 4:
                decoded = (value + paeth(left, up, up_left)) & 255
            else:
                raise RuntimeError(f"READABILITY_PNG_FILTER_UNSUPPORTED:{filter_type}")
            row[i] = decoded
        if y in needed_rows:
            rows[y] = bytes(row)
        prior = row
    return width, height, channels, rows


def probe_samples(probe: dict) -> list[tuple[float, float, float, float, int]]:
    ax, ay = probe["aPx4x"]
    bx, by = probe["bPx4x"]
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 1:
        raise RuntimeError(f"READABILITY_PROBE_TOO_SHORT:{probe['id']}")
    tx, ty = dx / length, dy / length
    nx, ny = -ty, tx
    band = int(round(probe["searchBandPx4x"]))
    samples = []
    for index in range(SAMPLES_PER_PROBE):
        t = 0.08 + (0.84 * index / max(1, SAMPLES_PER_PROBE - 1))
        samples.append((ax + dx * t, ay + dy * t, nx, ny, band))
    return samples


def required_rows(spec: dict, height: int | None = None) -> set[int]:
    rows: set[int] = set()
    for probe in spec["probes"]:
        for x, y, nx, ny, band in probe_samples(probe):
            del x, nx
            for offset in range(-band - 2, band + 3):
                py = int(round(y + ny * offset))
                if height is None or 0 <= py < height:
                    rows.add(py)
    return rows


def luma(rows: dict[int, bytes], width: int, channels: int, x: float, y: float) -> float:
    xi = min(width - 1, max(0, int(round(x))))
    yi = int(round(y))
    row = rows.get(yi)
    if row is None:
        raise RuntimeError(f"READABILITY_ROW_NOT_RETAINED:{yi}")
    pos = xi * channels
    r, g, b = row[pos], row[pos+1], row[pos+2]
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def analyze_probe(probe: dict, width: int, height: int, channels: int, rows: dict[int, bytes], factor: int) -> dict:
    contrasts: list[float] = []
    offsets: list[float] = []
    threshold = float(probe["contrastThreshold"])
    for x, y, nx, ny, band in probe_samples(probe):
        best_gradient = -1.0
        best_offset = 0
        for offset in range(-band + 1, band):
            x_minus = x + nx * (offset - 1)
            y_minus = y + ny * (offset - 1)
            x_plus = x + nx * (offset + 1)
            y_plus = y + ny * (offset + 1)
            if not (0 <= x_minus < width and 0 <= x_plus < width and 0 <= y_minus < height and 0 <= y_plus < height):
                continue
            gradient = abs(luma(rows, width, channels, x_plus, y_plus) - luma(rows, width, channels, x_minus, y_minus)) / 2.0
            if gradient > best_gradient:
                best_gradient = gradient
                best_offset = offset
        if best_gradient >= 0:
            contrasts.append(best_gradient)
            offsets.append(abs(best_offset) / factor)
    if not contrasts:
        raise RuntimeError(f"READABILITY_NO_SAMPLES:{probe['id']}")
    return {
        "id": probe["id"],
        "role": probe["role"],
        "samples": len(contrasts),
        "contrastThreshold": threshold,
        "edgeRecall": sum(value >= threshold for value in contrasts) / len(contrasts),
        "medianPeakContrast": statistics.median(contrasts),
        "p10PeakContrast": percentile(contrasts, 0.10),
        "medianEdgeOffsetCanonicalPx": statistics.median(offsets),
        "p95EdgeOffsetCanonicalPx": percentile(offsets, 0.95),
    }


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    factor = int(spec["supersampleFactor"])
    if factor != 4:
        raise RuntimeError(f"READABILITY_SUPERSAMPLE_EXPECTED_4:{factor}")
    provisional_rows = required_rows(spec)
    width, height, channels, rows = parse_png(PNG, provisional_rows)
    expected = tuple(value * factor for value in spec["canonicalViewportPx"])
    if (width, height) != expected:
        raise RuntimeError(f"READABILITY_VIEWPORT_MISMATCH:{width}x{height}:{expected}")
    missing_rows = required_rows(spec, height) - rows.keys()
    if missing_rows:
        raise RuntimeError(f"READABILITY_ROWS_MISSING:{len(missing_rows)}")

    results = [analyze_probe(probe, width, height, channels, rows, factor) for probe in spec["probes"]]
    recalls = [item["edgeRecall"] for item in results]
    medians = [item["medianPeakContrast"] for item in results]
    offsets = [item["medianEdgeOffsetCanonicalPx"] for item in results]
    payload = {
        "schemaVersion": "ReadabilityReport 1.0",
        "status": "MEASURED",
        "sourcePng": str(PNG),
        "viewportPx": [width, height],
        "supersampleFactor": factor,
        "summary": {
            "meanEdgeRecall": sum(recalls) / len(recalls),
            "medianProbeContrast": statistics.median(medians),
            "medianProbeEdgeOffsetCanonicalPx": statistics.median(offsets),
        },
        "probes": results,
        "policy": {
            "softGate": True,
            "measurement": "peak local sRGB-luma gradient within metric seam corridor",
            "textureAwayFromExpectedSeamDoesNotScore": True,
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
