"""Internal implementation package for the public tools.agent facade."""
from __future__ import annotations

from pathlib import Path

from . import impl as _impl

# The implementation moved one directory deeper than its original tools/agent.py
# location. Keep repository-root semantics explicit at the package boundary.
_impl.ROOT = Path(__file__).resolve().parents[2]

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)
