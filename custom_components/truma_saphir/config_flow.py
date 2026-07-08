from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.helpers import selector

from . import DOMAIN
from .climate import (
    CONF_COLD_TOLERANCE,
    CONF_COMMAND_DEBOUNCE,
    CONF_COOLING_TEMPERATURE,
    CONF_EXTERNAL_IDLE_HVAC_MODE,
    CONF_EXTERNAL_OPERATION_MODE,
    CONF_EXTERNAL_THERMOSTAT,
    CONF_HEATING_TEMPERATURE,
    CONF_HOT_TOLERANCE,
    CONF_MIN_CYCLE_DURATION,
    CONF_POWER_GUARD_ENTITY,
    CONF_POWER_GUARD_ON_SERVICE,
    CONF_POWER_GUARD_ON_SERVICE_DATA,
    CONF_POWER_GUARD_ON_STATE,
    CONF_SEND_TOPIC,
    CONF_TARGET_SENSOR,
    DEFAULT_COLD_TOLERANCE,
    DEFAULT_COMMAND_DEBOUNCE,
    DEFAULT_COOLING_TEMPERATURE,
    DEFAULT_EXTERNAL_IDLE_HVAC_MODE,
    DEFAULT_EXTERNAL_OPERATION_MODE,
    DEFAULT_EXTERNAL_THERMOSTAT,
    DEFAULT_HEATING_TEMPERATURE,
    DEFAULT_HOT_TOLERANCE,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_NAME,
    DEFAULT_POWER_GUARD_ENTITY,
    DEFAULT_POWER_GUARD_ON_STATE,
    DEFAULT_SEND_TOPIC,
    DEFAULT_TARGET_SENSOR,
    DEFAULT_UNIQUE_ID,
    EXTERNAL_OPERATION_MODES,
    EXTERNAL_IDLE_HVAC_MODES,
)


POWER_GUARD_DOMAINS = ["input_select", "switch", "input_boolean"]


class TrumaSaphirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return TrumaSaphirOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            data = dict(user_input)
            for optional_text_key in (
                CONF_TARGET_SENSOR,
                CONF_POWER_GUARD_ENTITY,
                CONF_POWER_GUARD_ON_STATE,
            ):
                if data.get(optional_text_key) == "":
                    data.pop(optional_text_key)

            data[CONF_UNIQUE_ID] = DEFAULT_UNIQUE_ID
            _apply_power_guard_defaults(data)

            await self.async_set_unique_id(DEFAULT_UNIQUE_ID)
            self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(user_input),
            errors=errors,
        )

    def _schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        defaults = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(
                    CONF_SEND_TOPIC,
                    default=defaults.get(CONF_SEND_TOPIC, DEFAULT_SEND_TOPIC),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_TARGET_SENSOR,
                    default=defaults.get(CONF_TARGET_SENSOR, DEFAULT_TARGET_SENSOR),
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    CONF_POWER_GUARD_ENTITY,
                    default=defaults.get(CONF_POWER_GUARD_ENTITY, DEFAULT_POWER_GUARD_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=POWER_GUARD_DOMAINS)
                ),
                vol.Optional(
                    CONF_POWER_GUARD_ON_STATE,
                    default=defaults.get(CONF_POWER_GUARD_ON_STATE, DEFAULT_POWER_GUARD_ON_STATE),
                ): _power_guard_state_selector(
                    self.hass, defaults.get(CONF_POWER_GUARD_ENTITY, DEFAULT_POWER_GUARD_ENTITY)
                ),
                vol.Required(
                    CONF_EXTERNAL_THERMOSTAT,
                    default=defaults.get(CONF_EXTERNAL_THERMOSTAT, DEFAULT_EXTERNAL_THERMOSTAT),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_EXTERNAL_OPERATION_MODE,
                    default=defaults.get(
                        CONF_EXTERNAL_OPERATION_MODE, DEFAULT_EXTERNAL_OPERATION_MODE
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=EXTERNAL_OPERATION_MODES)
                ),
                vol.Required(
                    CONF_EXTERNAL_IDLE_HVAC_MODE,
                    default=defaults.get(
                        CONF_EXTERNAL_IDLE_HVAC_MODE, DEFAULT_EXTERNAL_IDLE_HVAC_MODE
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=EXTERNAL_IDLE_HVAC_MODES)
                ),
            }
        )


class TrumaSaphirOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = dict(user_input)
            for optional_text_key in (
                CONF_TARGET_SENSOR,
                CONF_POWER_GUARD_ENTITY,
                CONF_POWER_GUARD_ON_STATE,
            ):
                if options.get(optional_text_key) == "":
                    options.pop(optional_text_key)
            _apply_power_guard_defaults(options)
            return self.async_create_entry(title="", data=options)

        defaults = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.hass, defaults),
        )


def _options_schema(hass, defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_SEND_TOPIC,
                default=defaults.get(CONF_SEND_TOPIC, DEFAULT_SEND_TOPIC),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_TARGET_SENSOR,
                default=defaults.get(CONF_TARGET_SENSOR, DEFAULT_TARGET_SENSOR),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_POWER_GUARD_ENTITY,
                default=defaults.get(CONF_POWER_GUARD_ENTITY, DEFAULT_POWER_GUARD_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=POWER_GUARD_DOMAINS)),
            vol.Optional(
                CONF_POWER_GUARD_ON_STATE,
                default=defaults.get(CONF_POWER_GUARD_ON_STATE, DEFAULT_POWER_GUARD_ON_STATE),
            ): _power_guard_state_selector(
                hass, defaults.get(CONF_POWER_GUARD_ENTITY, DEFAULT_POWER_GUARD_ENTITY)
            ),
            vol.Required(
                CONF_EXTERNAL_THERMOSTAT,
                default=defaults.get(CONF_EXTERNAL_THERMOSTAT, DEFAULT_EXTERNAL_THERMOSTAT),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXTERNAL_OPERATION_MODE,
                default=defaults.get(CONF_EXTERNAL_OPERATION_MODE, DEFAULT_EXTERNAL_OPERATION_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=EXTERNAL_OPERATION_MODES)
            ),
            vol.Required(
                CONF_EXTERNAL_IDLE_HVAC_MODE,
                default=defaults.get(CONF_EXTERNAL_IDLE_HVAC_MODE, DEFAULT_EXTERNAL_IDLE_HVAC_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=EXTERNAL_IDLE_HVAC_MODES)
            ),
            vol.Required(
                CONF_COLD_TOLERANCE,
                default=defaults.get(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, step=0.1, mode="box")
            ),
            vol.Required(
                CONF_HOT_TOLERANCE,
                default=defaults.get(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, step=0.1, mode="box")
            ),
            vol.Required(
                CONF_MIN_CYCLE_DURATION,
                default=defaults.get(CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=3600, step=1, mode="box")
            ),
            vol.Required(
                CONF_COOLING_TEMPERATURE,
                default=defaults.get(CONF_COOLING_TEMPERATURE, DEFAULT_COOLING_TEMPERATURE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=16, max=31, step=1, mode="box")
            ),
            vol.Required(
                CONF_HEATING_TEMPERATURE,
                default=defaults.get(CONF_HEATING_TEMPERATURE, DEFAULT_HEATING_TEMPERATURE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=16, max=31, step=1, mode="box")
            ),
            vol.Required(
                CONF_COMMAND_DEBOUNCE,
                default=defaults.get(CONF_COMMAND_DEBOUNCE, DEFAULT_COMMAND_DEBOUNCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, step=0.1, mode="box")
            ),
        }
    )


def _power_guard_state_selector(hass, entity_id: str | None):
    state_options = _entity_option_values(hass, entity_id)
    if state_options:
        return selector.SelectSelector(selector.SelectSelectorConfig(options=state_options))
    return selector.TextSelector()


def _entity_option_values(hass, entity_id: str | None) -> list[str]:
    if not entity_id:
        return []
    state = hass.states.get(entity_id)
    if state is None:
        return []
    options = state.attributes.get("options")
    if not isinstance(options, list):
        return []
    return [str(option) for option in options]


def _apply_power_guard_defaults(data: dict[str, Any]) -> None:
    entity_id = data.get(CONF_POWER_GUARD_ENTITY)
    if not entity_id:
        data[CONF_POWER_GUARD_ON_SERVICE_DATA] = {}
        return

    service = data.get(CONF_POWER_GUARD_ON_SERVICE)
    if service:
        data[CONF_POWER_GUARD_ON_SERVICE_DATA] = {"entity_id": entity_id}
        if service == "input_select.select_option":
            data[CONF_POWER_GUARD_ON_SERVICE_DATA]["option"] = data.get(
                CONF_POWER_GUARD_ON_STATE, DEFAULT_POWER_GUARD_ON_STATE
            )
        return

    if entity_id.split(".", 1)[0] == "input_select":
        data[CONF_POWER_GUARD_ON_SERVICE_DATA] = {
            "entity_id": entity_id,
            "option": data.get(CONF_POWER_GUARD_ON_STATE, DEFAULT_POWER_GUARD_ON_STATE),
        }
        return

    data[CONF_POWER_GUARD_ON_SERVICE_DATA] = {"entity_id": entity_id}
