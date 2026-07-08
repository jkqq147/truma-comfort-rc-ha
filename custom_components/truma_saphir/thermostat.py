from __future__ import annotations

from dataclasses import dataclass


IDLE_HVAC_MODES = ("fan_only", "off")
EXTERNAL_OPERATION_MODES = ("cool", "heat")


@dataclass(frozen=True)
class ControlState:
    hvac_mode: str
    temperature: int | None
    fan_mode: str | None
    hvac_action: str


def resolve_external_control_state(
    *,
    requested_hvac_mode: str,
    external_operation_mode: str = "cool",
    current_temperature: float | None,
    target_temperature: float,
    fan_mode: str,
    previous_hvac_mode: str | None,
    idle_hvac_mode: str,
    cold_tolerance: float,
    hot_tolerance: float,
    cooling_temperature: int = 16,
    heating_temperature: int = 31,
) -> ControlState:
    if idle_hvac_mode not in IDLE_HVAC_MODES:
        raise ValueError(f"Unsupported idle HVAC mode: {idle_hvac_mode}")
    if external_operation_mode not in EXTERNAL_OPERATION_MODES:
        raise ValueError(f"Unsupported external operation mode: {external_operation_mode}")

    if requested_hvac_mode == "auto" and current_temperature is None:
        return ControlState("auto", int(target_temperature), None, "idle")

    if requested_hvac_mode == "auto":
        requested_hvac_mode = external_operation_mode

    if requested_hvac_mode == "cool":
        active = _cooling_should_run(
            current_temperature=current_temperature,
            target_temperature=target_temperature,
            previous_hvac_mode=previous_hvac_mode,
            cold_tolerance=cold_tolerance,
            hot_tolerance=hot_tolerance,
        )
        if active:
            return ControlState("cool", cooling_temperature, fan_mode, "cooling")
        return _idle_state(idle_hvac_mode, fan_mode)

    if requested_hvac_mode == "heat":
        active = _heating_should_run(
            current_temperature=current_temperature,
            target_temperature=target_temperature,
            previous_hvac_mode=previous_hvac_mode,
            cold_tolerance=cold_tolerance,
            hot_tolerance=hot_tolerance,
        )
        if active:
            return ControlState("heat", heating_temperature, fan_mode, "heating")
        return _idle_state(idle_hvac_mode, fan_mode)

    if requested_hvac_mode == "fan_only":
        return ControlState("fan_only", None, fan_mode, "fan")
    if requested_hvac_mode == "off":
        return ControlState("off", None, None, "off")
    return ControlState(requested_hvac_mode, int(target_temperature), fan_mode, "idle")


def _cooling_should_run(
    *,
    current_temperature: float | None,
    target_temperature: float,
    previous_hvac_mode: str | None,
    cold_tolerance: float,
    hot_tolerance: float,
) -> bool:
    if current_temperature is None:
        return True
    if previous_hvac_mode == "cool":
        return current_temperature > target_temperature - cold_tolerance
    return current_temperature >= target_temperature + hot_tolerance


def _heating_should_run(
    *,
    current_temperature: float | None,
    target_temperature: float,
    previous_hvac_mode: str | None,
    cold_tolerance: float,
    hot_tolerance: float,
) -> bool:
    if current_temperature is None:
        return True
    if previous_hvac_mode == "heat":
        return current_temperature < target_temperature + hot_tolerance
    return current_temperature <= target_temperature - cold_tolerance


def _idle_state(idle_hvac_mode: str, fan_mode: str) -> ControlState:
    if idle_hvac_mode == "off":
        return ControlState("off", None, None, "idle")
    return ControlState("fan_only", None, fan_mode, "fan")
