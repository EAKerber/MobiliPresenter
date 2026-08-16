from __future__ import annotations

import re
from dataclasses import dataclass

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class _SemanticId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _ID_RE.fullmatch(self.value):
            raise RuntimeError(f"{self.__class__.__name__.upper()}_INVALID")

    def __str__(self) -> str:
        return self.value


class RoleId(_SemanticId):
    """Logical function identifier."""


class WorkerId(_SemanticId):
    """Persistent identifiable executor identifier."""


class SessionId(_SemanticId):
    """Ephemeral execution-session identifier."""
