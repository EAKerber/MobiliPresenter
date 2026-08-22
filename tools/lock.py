#!/usr/bin/env python3
"""Legacy `lock` CLI compatibility wrapper.

Canonical Coordination operations live in tools.coordination_cli. This module
exists only while the OperationalSemantics `lock` alias remains supported.
"""
from __future__ import annotations

from tools.coordination_cli import legacy_lock_main

LEGACY_LOCK_WRAPPER = True


def main(argv=None, *, authority_factory=None, environ=None):
    kwargs = {"environ": environ}
    if authority_factory is not None:
        kwargs["authority_factory"] = authority_factory
    return legacy_lock_main(argv, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
