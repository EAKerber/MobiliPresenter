from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MANIFEST = ROOT / "snapshot" / "mobile" / "manifest.json"
REQUIRED_SITE_FILES = {
    "index.html",
    "manufacturing.html",
    "DEPLOYMENT.json",
}
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024


class DeploymentError(RuntimeError):
    """Raised when the versioned deployment artifact fails validation."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reset_site() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)


def load_manifest() -> dict:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentError(f"Unable to read manifest: {MANIFEST}") from exc

    required = {
        "schemaVersion",
        "artifact",
        "decodedBytes",
        "sha256",
        "base64Length",
        "chunkCount",
        "chunks",
    }
    missing = sorted(required.difference(manifest))
    if missing:
        raise DeploymentError(f"Manifest missing keys: {', '.join(missing)}")
    if manifest["schemaVersion"] != "SnapshotChunks 1.0":
        raise DeploymentError(f"Unsupported manifest schema: {manifest['schemaVersion']}")
    if manifest["chunkCount"] != len(manifest["chunks"]):
        raise DeploymentError("Manifest chunkCount does not match chunks list")
    return manifest


def reconstruct_artifact(manifest: dict) -> bytes:
    encoded_parts: list[str] = []
    for index, chunk in enumerate(manifest["chunks"]):
        relative_path = PurePosixPath(chunk["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise DeploymentError(f"Unsafe chunk path at index {index}: {relative_path}")

        path = ROOT.joinpath(*relative_path.parts)
        try:
            content = path.read_text(encoding="ascii")
        except OSError as exc:
            raise DeploymentError(f"Unable to read chunk: {relative_path}") from exc

        actual_chars = len(content)
        actual_hash = sha256_bytes(content.encode("ascii"))
        if actual_chars != chunk["chars"]:
            raise DeploymentError(
                f"Chunk length mismatch for {relative_path}: "
                f"expected {chunk['chars']}, got {actual_chars}"
            )
        if actual_hash != chunk["sha256"]:
            raise DeploymentError(
                f"Chunk SHA-256 mismatch for {relative_path}: "
                f"expected {chunk['sha256']}, got {actual_hash}"
            )
        encoded_parts.append(content)

    encoded = "".join(encoded_parts)
    if len(encoded) != manifest["base64Length"]:
        raise DeploymentError(
            "Base64 length mismatch: "
            f"expected {manifest['base64Length']}, got {len(encoded)}"
        )

    try:
        artifact = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise DeploymentError("Artifact Base64 is invalid") from exc

    if len(artifact) != manifest["decodedBytes"]:
        raise DeploymentError(
            "Artifact byte length mismatch: "
            f"expected {manifest['decodedBytes']}, got {len(artifact)}"
        )
    actual_hash = sha256_bytes(artifact)
    if actual_hash != manifest["sha256"]:
        raise DeploymentError(
            "Artifact SHA-256 mismatch: "
            f"expected {manifest['sha256']}, got {actual_hash}"
        )
    return artifact


def validate_zip_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    path = PurePosixPath(name)
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise DeploymentError(f"Unsafe ZIP member: {name!r}")
    if path.is_absolute() or ".." in path.parts:
        raise DeploymentError(f"Unsafe ZIP member: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise DeploymentError(f"Symbolic links are not allowed in snapshot: {name!r}")


def extract_artifact(artifact: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
            infos = archive.infolist()
            uncompressed = sum(info.file_size for info in infos)
            if uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise DeploymentError(
                    f"Snapshot expands to {uncompressed} bytes, exceeding "
                    f"the {MAX_UNCOMPRESSED_BYTES}-byte limit"
                )
            for info in infos:
                validate_zip_member(info)
            archive.extractall(SITE)
    except zipfile.BadZipFile as exc:
        raise DeploymentError("Artifact is not a valid ZIP archive") from exc

    missing = sorted(name for name in REQUIRED_SITE_FILES if not (SITE / name).is_file())
    if missing:
        raise DeploymentError(f"Published site missing files: {', '.join(missing)}")


def publish_pending_page() -> None:
    shutil.copy2(ROOT / "pending.html", SITE / "index.html")


def main() -> None:
    reset_site()
    if not MANIFEST.is_file():
        publish_pending_page()
        print(f"Snapshot manifest pending: {MANIFEST.relative_to(ROOT)}")
        return

    manifest = load_manifest()
    artifact = reconstruct_artifact(manifest)
    extract_artifact(artifact)
    print(
        "Published verified snapshot "
        f"{manifest['artifact']} | bytes={len(artifact)} | sha256={sha256_bytes(artifact)}"
    )


if __name__ == "__main__":
    main()
