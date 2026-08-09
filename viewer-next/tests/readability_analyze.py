from __future__ import annotations

import json
import math
import statistics
import struct
import sys
import zlib
from pathlib import Path

SPEC_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mobilipresenter-readability-spec.json")
MANIFEST_PATH = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-readability-crops.json")
CROP_DIR = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-crops")
OUTPUT_PATH = Path(sys.argv[4] if len(sys.argv) > 4 else "/tmp/mobilipresenter-readability-report.json")
SAMPLES_PER_PROBE = 48


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def paeth(left: int, up: int, up_left: int) -> int:
    predictor = left + up - up_left
    dl = abs(predictor - left)
    du = abs(predictor - up)
    dul = abs(predictor - up_left)
    if dl <= du and dl <= dul:
        return left
    if du <= dul:
        return up
    return up_left


def decode_png(path: Path) -> tuple[int, int, int, list[bytes]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"READABILITY_NOT_PNG:{path}")
    offset = 8
    compressed = bytearray()
    width = height = bit_depth = color_type = interlace = None
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise RuntimeError("READABILITY_IHDR_MISSING")
    if bit_depth != 8 or color_type not in {2, 6} or interlace != 0:
        raise RuntimeError(f"READABILITY_PNG_FORMAT_UNSUPPORTED:{bit_depth}:{color_type}:{interlace}")
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    if len(raw) != height * (stride + 1):
        raise RuntimeError("READABILITY_PNG_DECOMPRESSED_SIZE_MISMATCH")
    rows: list[bytes] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = raw[cursor:cursor+stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(encoded):
            left = row[index-channels] if index >= channels else 0
            up = previous[index]
            up_left = previous[index-channels] if index >= channels else 0
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
            row[index] = decoded
        rows.append(bytes(row))
        previous = row
    return width, height, channels, rows


def luma(rows: list[bytes], width: int, channels: int, x: float, y: float) -> float:
    xi = min(width - 1, max(0, int(round(x))))
    yi = min(len(rows) - 1, max(0, int(round(y))))
    row = rows[yi]
    offset = xi * channels
    red, green, blue = row[offset], row[offset + 1], row[offset + 2]
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def analyze(probe: dict, entry: dict, factor: int) -> dict:
    png = CROP_DIR / entry["png"]
    width, height, channels, rows = decode_png(png)
    crop = entry["crop4x"]
    if (width, height) != (crop["widthPx"], crop["heightPx"]):
        raise RuntimeError(f"READABILITY_CROP_SIZE_MISMATCH:{probe['id']}")

    ax = probe["aPx4x"][0] - crop["xPx"]
    ay = probe["aPx4x"][1] - crop["yPx"]
    bx = probe["bPx4x"][0] - crop["xPx"]
    by = probe["bPx4x"][1] - crop["yPx"]
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 1:
        raise RuntimeError(f"READABILITY_PROBE_TOO_SHORT:{probe['id']}")
    normal_x, normal_y = -dy / length, dx / length
    band = int(round(probe["searchBandPx4x"]))
    contrasts: list[float] = []
    offsets: list[float] = []

    for sample_index in range(SAMPLES_PER_PROBE):
        t = 0.08 + 0.84 * sample_index / max(1, SAMPLES_PER_PROBE - 1)
        x = ax + dx * t
        y = ay + dy * t
        best_gradient = -1.0
        best_offset = 0
        for offset in range(-band + 1, band):
            minus_x, minus_y = x + normal_x * (offset - 1), y + normal_y * (offset - 1)
            plus_x, plus_y = x + normal_x * (offset + 1), y + normal_y * (offset + 1)
            if not (0 <= minus_x < width and 0 <= plus_x < width and 0 <= minus_y < height and 0 <= plus_y < height):
                continue
            gradient = abs(luma(rows, width, channels, plus_x, plus_y) - luma(rows, width, channels, minus_x, minus_y)) / 2.0
            if gradient > best_gradient:
                best_gradient = gradient
                best_offset = offset
        if best_gradient >= 0:
            contrasts.append(best_gradient)
            offsets.append(abs(best_offset) / factor)

    if not contrasts:
        raise RuntimeError(f"READABILITY_NO_SAMPLES:{probe['id']}")
    threshold = float(probe["contrastThreshold"])
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
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    factor = int(spec["supersampleFactor"])
    if factor != int(manifest["supersampleFactor"]):
        raise RuntimeError("READABILITY_FACTOR_MISMATCH")
    entries = {entry["probeId"]: entry for entry in manifest["entries"]}
    results = []
    for probe in spec["probes"]:
        entry = entries.get(probe["id"])
        if entry is None:
            raise RuntimeError(f"READABILITY_CAPTURE_MISSING:{probe['id']}")
        results.append(analyze(probe, entry, factor))

    recalls = [item["edgeRecall"] for item in results]
    contrasts = [item["medianPeakContrast"] for item in results]
    offsets = [item["medianEdgeOffsetCanonicalPx"] for item in results]
    payload = {
        "schemaVersion": "ReadabilityReport 1.0",
        "status": "MEASURED",
        "supersampleFactor": factor,
        "capturePolicy": "targeted-off-axis-4x-crops",
        "summary": {
            "meanEdgeRecall": sum(recalls) / len(recalls),
            "medianProbeContrast": statistics.median(contrasts),
            "medianProbeEdgeOffsetCanonicalPx": statistics.median(offsets),
        },
        "probes": results,
        "policy": {
            "softGate": True,
            "measurement": "peak local sRGB-luma gradient inside the metric seam corridor",
            "textureAwayFromExpectedSeamDoesNotScore": True,
            "full4xFramebufferRequired": False,
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
