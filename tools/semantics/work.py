from __future__ import annotations

from enum import Enum


class WorkStatus(str, Enum):
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    HANDOFF = "HANDOFF"
    DONE = "DONE"

    @classmethod
    def parse(cls, value: str) -> "WorkStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise RuntimeError("WORK_STATUS_INVALID") from exc

    @property
    def terminal(self) -> bool:
        return self is WorkStatus.DONE
