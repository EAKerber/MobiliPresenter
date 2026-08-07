from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent / "i1-package"
MANIFEST = PACKAGE / "manifest.json"
MAX_UNCOMPRESSED_BYTES = 5 * 1024 * 1024


class MaterializationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest() -> dict:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"Unable to read manifest: {MANIFEST}") from exc

    if manifest.get("schemaVersion") != "FixedViewI1Package 1.0":
        raise MaterializationError("Unsupported package schema")
    if manifest.get("chunkCount") != len(manifest.get("chunks", [])):
        raise MaterializationError("chunkCount does not match chunks list")
    return manifest


def reconstruct(manifest: dict) -> bytes:
    encoded_parts: list[str] = []
    for chunk in manifest["chunks"]:
        path = ROOT / PurePosixPath(chunk["path"])
        try:
            content = path.read_text(encoding="ascii")
        except OSError as exc:
            raise MaterializationError(f"Unable to read chunk: {path}") from exc
        if len(content) != chunk["chars"]:
            raise MaterializationError(f"Chunk length mismatch: {path}")
        if sha256_bytes(content.encode("ascii")) != chunk["sha256"]:
            raise MaterializationError(f"Chunk hash mismatch: {path}")
        encoded_parts.append(content)

    encoded = "".join(encoded_parts)
    if len(encoded) != manifest["base64Length"]:
        raise MaterializationError("Base64 length mismatch")

    try:
        artifact = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise MaterializationError("Invalid Base64 package") from exc

    if len(artifact) != manifest["decodedBytes"]:
        raise MaterializationError("Decoded byte length mismatch")
    if sha256_bytes(artifact) != manifest["sha256"]:
        raise MaterializationError("Artifact hash mismatch")
    return artifact


def validate_member(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    path = PurePosixPath(name)
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise MaterializationError(f"Unsafe ZIP member: {name!r}")
    if path.is_absolute() or ".." in path.parts:
        raise MaterializationError(f"Unsafe ZIP member: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise MaterializationError(f"Symbolic links are not allowed: {name!r}")
    return path


def extract(artifact: bytes, force: bool) -> list[Path]:
    written: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise MaterializationError("Package exceeds uncompressed size limit")
        members = [(info, validate_member(info)) for info in infos]

        conflicts = [
            ROOT.joinpath(*path.parts)
            for info, path in members
            if not info.is_dir() and ROOT.joinpath(*path.parts).exists()
        ]
        if conflicts and not force:
            preview = ", ".join(str(path.relative_to(ROOT)) for path in conflicts[:5])
            raise MaterializationError(
                f"Refusing to overwrite existing files ({preview}). Re-run with --force."
            )

        with tempfile.TemporaryDirectory(prefix="mobilipresenter-i1-") as tmp:
            staging = Path(tmp)
            archive.extractall(staging)
            for info, path in members:
                if info.is_dir():
                    continue
                source = staging.joinpath(*path.parts)
                target = ROOT.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                written.append(target)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the verified Fixed View I1 source package.")
    parser.add_argument("--force", action="store_true", help="Overwrite previously materialized I1 files.")
    parser.add_argument("--verify-only", action="store_true", help="Verify the package without extracting it.")
    args = parser.parse_args()

    manifest = load_manifest()
    artifact = reconstruct(manifest)
    print(
        f"Verified {manifest['artifact']} | bytes={len(artifact)} | sha256={sha256_bytes(artifact)}"
    )
    if args.verify_only:
        return

    written = extract(artifact, force=args.force)
    print(f"Materialized {len(written)} files under {ROOT}")


if __name__ == "__main__":
    main()
