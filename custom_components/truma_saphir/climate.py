from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, CONF_UNIQUE_ID, UnitOfTemperature
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .code_table import CodeTable, CodeTableError
from .thermostat import ControlState, resolve_external_control_state


_LOGGER = logging.getLogger(__name__)

CONF_CODE_TABLE = "code_table"
CONF_SEND_TOPIC = "send_topic"
CONF_TARGET_SENSOR = "target_sensor"
CONF_TARGET_SENSOR_MAX_AGE = "target_sensor_max_age"
CONF_INITIAL_TEMPERATURE = "initial_temperature"
CONF_INITIAL_FAN_MODE = "initial_fan_mode"
CONF_SEND_REPEATS = "send_repeats"
CONF_REPEAT_DELAY = "repeat_delay"
CONF_COMMAND_DEBOUNCE = "command_debounce"
CONF_MQTT_QOS = "mqtt_qos"
CONF_POWER_GUARD_ENTITY = "power_guard_entity"
CONF_POWER_GUARD_ON_STATE = "power_guard_on_state"
CONF_POWER_GUARD_ON_SERVICE = "power_guard_on_service"
CONF_POWER_GUARD_ON_SERVICE_DATA = "power_guard_on_service_data"
CONF_POWER_GUARD_DELAY = "power_guard_delay"
CONF_EXTERNAL_THERMOSTAT = "external_thermostat"
CONF_EXTERNAL_OPERATION_MODE = "external_operation_mode"
CONF_EXTERNAL_IDLE_HVAC_MODE = "external_idle_hvac_mode"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_MIN_CYCLE_DURATION = "min_cycle_duration"
CONF_COOLING_TEMPERATURE = "cooling_temperature"
CONF_HEATING_TEMPERATURE = "heating_temperature"

DEFAULT_NAME = "Truma Comfort RC"
DEFAULT_CODE_TABLE = str(Path(__file__).with_name("truma_saphir_codes.csv"))
DEFAULT_SEND_TOPIC = "IRMINI1b50/send"
DEFAULT_TARGET_SENSOR = "sensor.combined_indoor_temperature"
DEFAULT_TARGET_SENSOR_MAX_AGE = 1800.0
DEFAULT_TEMPERATURE = 26
DEFAULT_FAN_MODE = "high"
DEFAULT_UNIQUE_ID = "truma_saphir_ir_climate"
DEFAULT_SEND_REPEATS = 2
DEFAULT_REPEAT_DELAY = 1.0
DEFAULT_COMMAND_DEBOUNCE = 0.8
DEFAULT_MQTT_QOS = 0
DEFAULT_POWER_GUARD_ENTITY = "input_select.victron_mode"
DEFAULT_POWER_GUARD_ON_STATE = "开机"
DEFAULT_POWER_GUARD_ON_SERVICE = "input_select.select_option"
DEFAULT_POWER_GUARD_DELAY = 5.0
DEFAULT_EXTERNAL_THERMOSTAT = True
DEFAULT_EXTERNAL_OPERATION_MODE = HVACMode.COOL.value
DEFAULT_EXTERNAL_IDLE_HVAC_MODE = HVACMode.FAN_ONLY.value
DEFAULT_COLD_TOLERANCE = 1.0
DEFAULT_HOT_TOLERANCE = 1.0
DEFAULT_MIN_CYCLE_DURATION = 60.0
DEFAULT_COOLING_TEMPERATURE = 16
DEFAULT_HEATING_TEMPERATURE = 31

HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.AUTO,
    HVACMode.FAN_ONLY,
]
EXTERNAL_THERMOSTAT_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.FAN_ONLY,
]
FAN_MODES = ["low", "medium", "high"]
EXTERNAL_OPERATION_MODES = [HVACMode.COOL.value, HVACMode.HEAT.value]
EXTERNAL_IDLE_HVAC_MODES = [HVACMode.FAN_ONLY.value, HVACMode.OFF.value]

HVAC_ACTIONS = {
    "off": "off",
    "idle": "idle",
    "cooling": "cooling",
    "heating": "heating",
    "fan": "fan",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CODE_TABLE, default=DEFAULT_CODE_TABLE): cv.string,
        vol.Optional(CONF_SEND_TOPIC, default=DEFAULT_SEND_TOPIC): cv.string,
        vol.Optional(CONF_TARGET_SENSOR, default=DEFAULT_TARGET_SENSOR): cv.entity_id,
        vol.Optional(
            CONF_TARGET_SENSOR_MAX_AGE, default=DEFAULT_TARGET_SENSOR_MAX_AGE
        ): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_INITIAL_TEMPERATURE, default=DEFAULT_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=16, max=31)
        ),
        vol.Optional(CONF_INITIAL_FAN_MODE, default=DEFAULT_FAN_MODE): vol.In(FAN_MODES),
        vol.Optional(CONF_SEND_REPEATS, default=DEFAULT_SEND_REPEATS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=5)
        ),
        vol.Optional(CONF_REPEAT_DELAY, default=DEFAULT_REPEAT_DELAY): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional(CONF_COMMAND_DEBOUNCE, default=DEFAULT_COMMAND_DEBOUNCE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional(CONF_MQTT_QOS, default=DEFAULT_MQTT_QOS): vol.In([0, 1, 2]),
        vol.Optional(CONF_POWER_GUARD_ENTITY, default=DEFAULT_POWER_GUARD_ENTITY): cv.entity_id,
        vol.Optional(CONF_POWER_GUARD_ON_STATE, default=DEFAULT_POWER_GUARD_ON_STATE): cv.string,
        vol.Optional(CONF_POWER_GUARD_ON_SERVICE, default=DEFAULT_POWER_GUARD_ON_SERVICE): cv.service,
        vol.Optional(CONF_POWER_GUARD_ON_SERVICE_DATA, default={}): dict,
        vol.Optional(CONF_POWER_GUARD_DELAY, default=DEFAULT_POWER_GUARD_DELAY): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=120)
        ),
        vol.Optional(CONF_EXTERNAL_THERMOSTAT, default=DEFAULT_EXTERNAL_THERMOSTAT): cv.boolean,
        vol.Optional(
            CONF_EXTERNAL_OPERATION_MODE, default=DEFAULT_EXTERNAL_OPERATION_MODE
        ): vol.In(EXTERNAL_OPERATION_MODES),
        vol.Optional(
            CONF_EXTERNAL_IDLE_HVAC_MODE, default=DEFAULT_EXTERNAL_IDLE_HVAC_MODE
        ): vol.In(EXTERNAL_IDLE_HVAC_MODES),
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_COLD_TOLERANCE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_HOT_TOLERANCE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional(CONF_MIN_CYCLE_DURATION, default=DEFAULT_MIN_CYCLE_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=3600)
        ),
        vol.Optional(CONF_COOLING_TEMPERATURE, default=DEFAULT_COOLING_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=16, max=31)
        ),
        vol.Optional(CONF_HEATING_TEMPERATURE, default=DEFAULT_HEATING_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=16, max=31)
        ),
        vol.Optional(CONF_UNIQUE_ID, default=DEFAULT_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, entry, async_add_entities):
    await _async_setup_entity(hass, {**entry.data, **entry.options}, async_add_entities)


async def _async_setup_entity(hass, config, async_add_entities) -> None:
    table = await hass.async_add_executor_job(
        CodeTable.from_csv, config.get(CONF_CODE_TABLE, DEFAULT_CODE_TABLE)
    )
    async_add_entities(
        [
            TrumaSaphirClimate(
                name=config.get(CONF_NAME, DEFAULT_NAME),
                unique_id=config.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID),
                code_table=table,
                send_topic=config.get(CONF_SEND_TOPIC, DEFAULT_SEND_TOPIC),
                target_sensor=config.get(CONF_TARGET_SENSOR, DEFAULT_TARGET_SENSOR),
                target_sensor_max_age=config.get(
                    CONF_TARGET_SENSOR_MAX_AGE, DEFAULT_TARGET_SENSOR_MAX_AGE
                ),
                initial_temperature=config.get(CONF_INITIAL_TEMPERATURE, DEFAULT_TEMPERATURE),
                initial_fan_mode=config.get(CONF_INITIAL_FAN_MODE, DEFAULT_FAN_MODE),
                send_repeats=config.get(CONF_SEND_REPEATS, DEFAULT_SEND_REPEATS),
                repeat_delay=config.get(CONF_REPEAT_DELAY, DEFAULT_REPEAT_DELAY),
                command_debounce=config.get(CONF_COMMAND_DEBOUNCE, DEFAULT_COMMAND_DEBOUNCE),
                mqtt_qos=config.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS),
                power_guard_entity=config.get(CONF_POWER_GUARD_ENTITY, DEFAULT_POWER_GUARD_ENTITY),
                power_guard_on_state=config.get(
                    CONF_POWER_GUARD_ON_STATE, DEFAULT_POWER_GUARD_ON_STATE
                ),
                power_guard_on_service=config.get(CONF_POWER_GUARD_ON_SERVICE),
                power_guard_on_service_data=config.get(CONF_POWER_GUARD_ON_SERVICE_DATA, {}),
                power_guard_delay=config.get(CONF_POWER_GUARD_DELAY, DEFAULT_POWER_GUARD_DELAY),
                external_thermostat=config.get(
                    CONF_EXTERNAL_THERMOSTAT, DEFAULT_EXTERNAL_THERMOSTAT
                ),
                external_operation_mode=config.get(
                    CONF_EXTERNAL_OPERATION_MODE, DEFAULT_EXTERNAL_OPERATION_MODE
                ),
                external_idle_hvac_mode=config.get(
                    CONF_EXTERNAL_IDLE_HVAC_MODE, DEFAULT_EXTERNAL_IDLE_HVAC_MODE
                ),
                cold_tolerance=config.get(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE),
                hot_tolerance=config.get(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE),
                min_cycle_duration=config.get(
                    CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION
                ),
                cooling_temperature=config.get(
                    CONF_COOLING_TEMPERATURE, DEFAULT_COOLING_TEMPERATURE
                ),
                heating_temperature=config.get(
                    CONF_HEATING_TEMPERATURE, DEFAULT_HEATING_TEMPERATURE
                ),
            )
        ]
    )


class TrumaSaphirClimate(ClimateEntity, RestoreEntity):
    _attr_has_entity_name = False
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 31
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = HVAC_MODES
    _attr_fan_modes = FAN_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(
        self,
        name: str,
        unique_id: str,
        code_table: CodeTable,
        send_topic: str,
        target_sensor: str | None,
        target_sensor_max_age: float,
        initial_temperature: int,
        initial_fan_mode: str,
        send_repeats: int,
        repeat_delay: float,
        command_debounce: float,
        mqtt_qos: int,
        power_guard_entity: str | None,
        power_guard_on_state: str,
        power_guard_on_service: str | None,
        power_guard_on_service_data: dict[str, Any],
        power_guard_delay: float,
        external_thermostat: bool,
        external_operation_mode: str,
        external_idle_hvac_mode: str,
        cold_tolerance: float,
        hot_tolerance: float,
        min_cycle_duration: float,
        cooling_temperature: int,
        heating_temperature: int,
    ) -> None:
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._code_table = code_table
        self._send_topic = send_topic
        self._target_sensor = target_sensor
        self._target_sensor_max_age = target_sensor_max_age
        self._send_repeats = send_repeats
        self._repeat_delay = repeat_delay
        self._command_debounce = command_debounce
        self._mqtt_qos = mqtt_qos
        self._power_guard_entity = power_guard_entity
        self._power_guard_on_state = power_guard_on_state
        self._power_guard_on_service = power_guard_on_service
        self._power_guard_on_service_data = dict(power_guard_on_service_data)
        self._power_guard_delay = power_guard_delay
        self._external_thermostat = external_thermostat
        self._external_operation_mode = external_operation_mode
        self._external_idle_hvac_mode = external_idle_hvac_mode
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._min_cycle_duration = min_cycle_duration
        self._cooling_temperature = cooling_temperature
        self._heating_temperature = heating_temperature
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = "off"
        self._attr_hvac_modes = (
            EXTERNAL_THERMOSTAT_HVAC_MODES if external_thermostat else HVAC_MODES
        )
        self._attr_target_temperature = initial_temperature
        self._attr_fan_mode = initial_fan_mode
        self._pending_task: asyncio.Task | None = None
        self._remove_sensor_listener = None
        self._last_control_state: ControlState | None = None
        self._last_cycle_change_time = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._external_thermostat and self._target_sensor is not None:
            self._remove_sensor_listener = async_track_state_change_event(
                self.hass, [self._target_sensor], self._async_sensor_changed
            )
        if (last_state := await self.async_get_last_state()) is None:
            return

        if last_state.state in {mode.value for mode in self._attr_hvac_modes}:
            self._attr_hvac_mode = HVACMode(last_state.state)
        elif self._external_thermostat and last_state.state in {
            HVACMode.COOL.value,
            HVACMode.HEAT.value,
        }:
            self._attr_hvac_mode = HVACMode.AUTO
        if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(temperature)
        if (fan_mode := last_state.attributes.get("fan_mode")) in FAN_MODES:
            self._attr_fan_mode = fan_mode

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_sensor_listener is not None:
            self._remove_sensor_listener()
            self._remove_sensor_listener = None
        if self._pending_task is not None:
            self._pending_task.cancel()
            self._pending_task = None
        await super().async_will_remove_from_hass()

    @property
    def current_temperature(self):
        return self._read_current_temperature()

    def _read_current_temperature(self) -> float | None:
        if self._target_sensor is None:
            return None
        state = self.hass.states.get(self._target_sensor)
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        if self._target_sensor_max_age > 0:
            age = (datetime.now(timezone.utc) - state.last_updated).total_seconds()
            if age > self._target_sensor_max_age:
                return None
        try:
            return float(state.state)
        except ValueError:
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        if ATTR_TEMPERATURE not in kwargs:
            return
        self._attr_target_temperature = float(kwargs[ATTR_TEMPERATURE])
        self.async_write_ha_state()
        await self._schedule_send(force=True)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
        await self._schedule_send(force=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.error("Unsupported Truma HVAC mode in current configuration: %s", hvac_mode)
            return
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        if hvac_mode == HVACMode.OFF:
            await self._send_current_state(force=True)
        else:
            await self._schedule_send(force=True)

    async def async_turn_on(self) -> None:
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = HVACMode.AUTO if self._external_thermostat else HVACMode.COOL
        self.async_write_ha_state()
        await self._schedule_send(force=True)

    async def async_turn_off(self) -> None:
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()
        await self._send_current_state(force=True)

    async def _async_sensor_changed(self, event) -> None:
        if self._attr_hvac_mode in {HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT}:
            await self._schedule_send(force=False)

    async def _schedule_send(self, *, force: bool) -> None:
        if self._pending_task is not None:
            self._pending_task.cancel()
        self._pending_task = self.hass.loop.create_task(self._debounced_send(force=force))

    async def _debounced_send(self, *, force: bool) -> None:
        try:
            await asyncio.sleep(self._command_debounce)
            await self._send_current_state(force=force)
        except asyncio.CancelledError:
            raise
        finally:
            self._pending_task = None

    async def _send_current_state(self, *, force: bool) -> None:
        control_state = self._resolve_control_state()
        if not force and self._is_min_cycle_blocked(control_state):
            return

        if not force and self._is_same_control_state(control_state):
            self._set_hvac_action(control_state)
            self.async_write_ha_state()
            return

        if control_state.hvac_mode != HVACMode.OFF.value and not await self._ensure_power_guard():
            return

        try:
            payload = self._code_table.lookup(
                control_state.hvac_mode,
                control_state.temperature,
                control_state.fan_mode,
            )
        except CodeTableError as err:
            _LOGGER.error("%s", err)
            return

        _LOGGER.info(
            "Sending Truma Saphir command requested_mode=%s mode=%s temp=%s fan=%s payload=%s",
            self._attr_hvac_mode.value,
            control_state.hvac_mode,
            control_state.temperature,
            control_state.fan_mode,
            payload,
        )
        for attempt in range(self._send_repeats):
            await mqtt.async_publish(
                self.hass, self._send_topic, payload, qos=self._mqtt_qos, retain=False
            )
            if attempt + 1 < self._send_repeats:
                await asyncio.sleep(self._repeat_delay)
        if not self._is_same_control_state(control_state):
            self._last_cycle_change_time = time.monotonic()
        self._last_control_state = control_state
        self._set_hvac_action(control_state)
        self.async_write_ha_state()

    def _resolve_control_state(self) -> ControlState:
        if self._external_thermostat and self._attr_hvac_mode in {
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
        }:
            return resolve_external_control_state(
                requested_hvac_mode=self._attr_hvac_mode.value,
                external_operation_mode=self._external_operation_mode,
                current_temperature=self._read_current_temperature(),
                target_temperature=float(self._attr_target_temperature),
                fan_mode=self._attr_fan_mode,
                previous_hvac_mode=(
                    self._last_control_state.hvac_mode
                    if self._last_control_state is not None
                    else None
                ),
                idle_hvac_mode=self._external_idle_hvac_mode,
                cold_tolerance=self._cold_tolerance,
                hot_tolerance=self._hot_tolerance,
                cooling_temperature=self._cooling_temperature,
                heating_temperature=self._heating_temperature,
            )
        if self._attr_hvac_mode == HVACMode.OFF:
            return ControlState(HVACMode.OFF.value, None, None, "off")
        if self._attr_hvac_mode == HVACMode.FAN_ONLY:
            return ControlState(HVACMode.FAN_ONLY.value, None, self._attr_fan_mode, "fan")
        action = (
            "cooling"
            if self._attr_hvac_mode == HVACMode.COOL
            else "heating"
            if self._attr_hvac_mode == HVACMode.HEAT
            else "idle"
        )
        return ControlState(
            self._attr_hvac_mode.value,
            int(float(self._attr_target_temperature)),
            self._attr_fan_mode,
            action,
        )

    def _is_same_control_state(self, control_state: ControlState) -> bool:
        return self._last_control_state == control_state

    def _is_min_cycle_blocked(self, next_state: ControlState) -> bool:
        if (
            not self._external_thermostat
            or self._last_control_state is None
            or self._min_cycle_duration <= 0
            or self._is_same_control_state(next_state)
        ):
            return False

        if _compressor_active(self._last_control_state) == _compressor_active(next_state):
            return False

        elapsed = time.monotonic() - self._last_cycle_change_time
        if elapsed >= self._min_cycle_duration:
            return False

        _LOGGER.info(
            "Delaying Truma external thermostat transition for %.1fs due to min_cycle_duration %.1fs",
            self._min_cycle_duration - elapsed,
            self._min_cycle_duration,
        )
        return True

    def _set_hvac_action(self, control_state: ControlState) -> None:
        self._attr_hvac_action = HVAC_ACTIONS.get(control_state.hvac_action, "idle")

    async def _ensure_power_guard(self) -> bool:
        if self._power_guard_entity is None:
            return True

        state = self.hass.states.get(self._power_guard_entity)
        if state is not None and state.state == self._power_guard_on_state:
            return True

        service = self._power_guard_on_service or _infer_power_guard_service(
            self._power_guard_entity
        )
        if service is None:
            _LOGGER.error(
                "Power guard entity %s is not %s and no usable power guard service is configured",
                self._power_guard_entity,
                self._power_guard_on_state,
            )
            return False

        domain, service_name = service.split(".", 1)
        service_data = dict(self._power_guard_on_service_data)
        service_data.setdefault("entity_id", self._power_guard_entity)
        if domain == "input_select":
            service_data.setdefault("option", self._power_guard_on_state)
        _LOGGER.info(
            "Calling power guard service %s for %s before Truma command",
            service,
            self._power_guard_entity,
        )
        await self.hass.services.async_call(domain, service_name, service_data, blocking=True)
        if self._power_guard_delay > 0:
            await asyncio.sleep(self._power_guard_delay)

        state = self.hass.states.get(self._power_guard_entity)
        if state is not None and state.state == self._power_guard_on_state:
            return True

        _LOGGER.error(
            "Power guard entity %s did not reach %s; Truma command was not sent",
            self._power_guard_entity,
            self._power_guard_on_state,
        )
        return False


def _infer_power_guard_service(entity_id: str) -> str | None:
    domain = entity_id.split(".", 1)[0]
    if domain == "input_select":
        return "input_select.select_option"
    if domain in {"switch", "input_boolean"}:
        return f"{domain}.turn_on"
    return None


def _compressor_active(control_state: ControlState) -> bool:
    return control_state.hvac_mode in {HVACMode.COOL.value, HVACMode.HEAT.value}
