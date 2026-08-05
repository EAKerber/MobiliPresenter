from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
SNAPSHOT = ROOT / "snapshot" / "mobilipresenter-v7.0-i5-preview.zip"


def reset_site() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)


def publish_snapshot() -> None:
    with zipfile.ZipFile(SNAPSHOT) as archive:
        archive.extractall(SITE)


def publish_pending_page() -> None:
    shutil.copy2(ROOT / "pending.html", SITE / "index.html")


def main() -> None:
    reset_site()
    if SNAPSHOT.is_file():
        publish_snapshot()
        print(f"Published snapshot: {SNAPSHOT.name}")
    else:
        publish_pending_page()
        print(f"Snapshot pending: {SNAPSHOT}")


if __name__ == "__main__":
    main()
