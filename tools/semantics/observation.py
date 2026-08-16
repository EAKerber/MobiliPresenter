from __future__ import annotations

from enum import Enum


class ObservationStatus(str, Enum):
    PASS = "PASS"
    UNKNOWN = "UNKNOWN"
    FAIL = "FAIL"

    @classmethod
    def parse(cls, value: str) -> "ObservationStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise RuntimeError("OBSERVATION_STATUS_INVALID") from exc
