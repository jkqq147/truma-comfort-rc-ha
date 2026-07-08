from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components/truma_saphir/thermostat.py"


def load_module():
    spec = importlib.util.spec_from_file_location("truma_thermostat", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExternalThermostatTests(unittest.TestCase):
    def test_cooling_uses_minimum_temperature_when_room_is_too_hot(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="cool",
            current_temperature=27,
            target_temperature=25,
            fan_mode="high",
            previous_hvac_mode=None,
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "cool")
        self.assertEqual(state.temperature, 16)
        self.assertEqual(state.fan_mode, "high")
        self.assertEqual(state.hvac_action, "cooling")

    def test_cooling_switches_to_fan_only_below_lower_tolerance(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="cool",
            current_temperature=23.9,
            target_temperature=25,
            fan_mode="medium",
            previous_hvac_mode="cool",
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "fan_only")
        self.assertIsNone(state.temperature)
        self.assertEqual(state.fan_mode, "medium")
        self.assertEqual(state.hvac_action, "fan")

    def test_cooling_stays_active_inside_tolerance_band_after_compressor_started(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="cool",
            current_temperature=25.4,
            target_temperature=25,
            fan_mode="low",
            previous_hvac_mode="cool",
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "cool")
        self.assertEqual(state.temperature, 16)
        self.assertEqual(state.hvac_action, "cooling")

    def test_heating_uses_maximum_temperature_when_room_is_too_cold(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="heat",
            current_temperature=21,
            target_temperature=23,
            fan_mode="high",
            previous_hvac_mode=None,
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "heat")
        self.assertEqual(state.temperature, 31)
        self.assertEqual(state.fan_mode, "high")
        self.assertEqual(state.hvac_action, "heating")

    def test_heating_switches_to_configured_off_idle_mode_above_upper_tolerance(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="heat",
            current_temperature=24.2,
            target_temperature=23,
            fan_mode="high",
            previous_hvac_mode="heat",
            idle_hvac_mode="off",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "off")
        self.assertIsNone(state.temperature)
        self.assertIsNone(state.fan_mode)
        self.assertEqual(state.hvac_action, "idle")

    def test_auto_uses_configured_cooling_direction_and_keeps_fan_mode(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="auto",
            external_operation_mode="cool",
            current_temperature=28,
            target_temperature=25,
            fan_mode="low",
            previous_hvac_mode=None,
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "cool")
        self.assertEqual(state.temperature, 16)
        self.assertEqual(state.fan_mode, "low")
        self.assertEqual(state.hvac_action, "cooling")

    def test_auto_uses_configured_heating_direction_and_keeps_fan_mode(self):
        thermostat = load_module()

        state = thermostat.resolve_external_control_state(
            requested_hvac_mode="auto",
            external_operation_mode="heat",
            current_temperature=20,
            target_temperature=23,
            fan_mode="medium",
            previous_hvac_mode=None,
            idle_hvac_mode="fan_only",
            cold_tolerance=1,
            hot_tolerance=1,
        )

        self.assertEqual(state.hvac_mode, "heat")
        self.assertEqual(state.temperature, 31)
        self.assertEqual(state.fan_mode, "medium")
        self.assertEqual(state.hvac_action, "heating")


if __name__ == "__main__":
    unittest.main()

