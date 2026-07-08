from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class CodeTableError(Exception):
    """Raised when a requested Truma state has no IR code."""


@dataclass(frozen=True)
class TrumaState:
    hvac_mode: str
    temperature: int | None
    fan_mode: str | None


class CodeTable:
    def __init__(self, codes: dict[TrumaState, str]) -> None:
        self._codes = codes

    @classmethod
    def from_csv(cls, path: str | Path) -> CodeTable:
        codes: dict[TrumaState, str] = {}
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                state = _row_to_state(row)
                if state is not None:
                    codes[state] = row["source_code"].strip()
        return cls(codes)

    def lookup(self, hvac_mode: str, temperature: int | None, fan_mode: str | None) -> str:
        state = _requested_state(hvac_mode, temperature, fan_mode)
        try:
            return self._codes[state]
        except KeyError as err:
            raise CodeTableError(
                f"Unsupported Truma state: mode={hvac_mode}, temp={temperature}, fan={fan_mode}"
            ) from err


def _row_to_state(row: dict[str, str]) -> TrumaState | None:
    power = row["power"].strip().lower()
    mode = row["mode"].strip()
    fan = row["fan"].strip().lower() or None
    temp = int(row["temperature_c"]) if row["temperature_c"].strip() else None

    if power == "off":
        return TrumaState("off", None, None)
    if mode == "Cooling":
        return TrumaState("cool", temp, fan)
    if mode == "Heating":
        return TrumaState("heat", temp, fan)
    if mode == "Automatic":
        return TrumaState("auto", temp, None)
    if mode == "Circulated air":
        return TrumaState("fan_only", None, fan)
    return None


def _requested_state(hvac_mode: str, temperature: int | None, fan_mode: str | None) -> TrumaState:
    mode = hvac_mode.lower()
    fan = fan_mode.lower() if fan_mode else None
    temp = int(temperature) if temperature is not None else None

    if mode == "off":
        return TrumaState("off", None, None)
    if mode in {"cool", "heat"}:
        return TrumaState(mode, temp, fan)
    if mode == "auto":
        return TrumaState("auto", temp, None)
    if mode == "fan_only":
        return TrumaState("fan_only", None, fan)
    raise CodeTableError(f"Unsupported Truma state: mode={hvac_mode}, temp={temperature}, fan={fan_mode}")
