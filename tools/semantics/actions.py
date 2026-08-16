from __future__ import annotations

from enum import Enum


class OperationalAction(str, Enum):
    CONTINUE = "CONTINUE"
    RECONCILE = "RECONCILE"
    HANDOFF = "HANDOFF"
    PAUSE = "PAUSE"
    NEEDS_HUMAN = "NEEDS_HUMAN"

    @classmethod
    def parse(cls, value: str) -> "OperationalAction":
        try:
            return cls(value)
        except ValueError as exc:
            raise RuntimeError("OPERATIONAL_ACTION_INVALID") from exc
