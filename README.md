# Truma Comfort RC IR Climate for Home Assistant

Home Assistant custom climate platform for the Truma Comfort RC air conditioner controlled through an MQTT infrared bridge.

Chinese documentation: [README.zh-Hans.md](README.zh-Hans.md)

The integration exposes a single standard `climate` entity and uses a bundled CSV code table to send complete IR state codes such as cooling mode, target temperature, and fan speed.

This repository is intentionally scoped to the Truma Comfort RC remote/code table documented in [docs/truma-comfort-rc-manual-2018-06.pdf](docs/truma-comfort-rc-manual-2018-06.pdf). It is not intended to be a generic Truma HVAC framework.

## Features

- Standard Home Assistant `climate` entity
- UI config flow and YAML configuration support
- Modes: `off`, `cool`, `heat`, `auto`, `fan_only`
- External thermostat mode exposes `off`, `auto`, and `fan_only` by default
- Temperature range: 16-31 C
- Fan modes: `low`, `medium`, `high`
- External thermostat control using the Home Assistant temperature sensor
- Bundled CSV-backed IR code table
- Repeat sending for unreliable IR links
- Optional power guard for inverters, shore-power relays, or other upstream power controls
- Optimistic state model for IR devices without feedback

## UI Setup

1. Copy `custom_components/truma_saphir` to Home Assistant `/config/custom_components/`.
2. Restart Home Assistant Core.
3. Go to Settings -> Devices & services -> Add Integration -> Truma Comfort RC IR Climate.
4. Keep the defaults for this setup, or adjust the MQTT topic, temperature sensor, and power guard fields.

Do not configure the same physical air conditioner in both YAML and the UI with the same `unique_id`, unless you intentionally want duplicate entities during migration.

## YAML Configuration

```yaml
climate:
  - platform: truma_saphir
    name: Truma Comfort RC
    unique_id: truma_saphir_ir_climate
    send_topic: IRMINI1b50/send
    target_sensor: sensor.combined_indoor_temperature

    external_thermostat: true
    external_operation_mode: cool
    external_idle_hvac_mode: fan_only

    power_guard_entity: input_select.victron_mode
    power_guard_on_state: "开机"
```

## External Thermostat

External thermostat control is enabled by default. In this mode, the Home Assistant target temperature is the desired cabin temperature, not the temperature sent to the Truma unit.

When external thermostat control is enabled, the Home Assistant climate entity exposes `auto`, `fan_only`, and `off`. The `auto` mode uses `external_operation_mode` to decide whether this setup is currently cooling or heating. It does not automatically switch between cooling and heating.

When `external_operation_mode` is `cool`, `auto` sends the Truma cooling command at `16 C` while cooling is needed. When `external_operation_mode` is `heat`, `auto` sends the Truma heating command at `31 C` while heating is needed. Fan speed remains effective because the generated command is still a cooling or heating IR state with the selected fan mode.

The default tolerance matches the previous `generic_thermostat` setup:

- Cooling starts at target + `1 C` and idles at target - `1 C`.
- Heating starts at target - `1 C` and idles at target + `1 C`.
- The minimum compressor cycle duration is `60` seconds.

When the target is reached, the default idle command is `fan_only`, which keeps airflow running and avoids the sharper off-to-compressor startup transition. Set `external_idle_hvac_mode: off` to turn the unit off instead.

## Power Guard

IR air conditioners in campers and overland vehicles often depend on an inverter or another upstream power source. Configure `power_guard_*` options to ensure that power is enabled before sending any non-off IR command.

When the requested mode is `off`, the integration skips the power guard and sends the off IR code directly.

When the requested mode is `cool`, `heat`, `auto`, or `fan_only`, the integration:

1. Checks `power_guard_entity`.
2. If it is already in `power_guard_on_state`, sends the IR command immediately.
3. Otherwise calls the configured or inferred power guard service.
4. Waits `power_guard_delay` seconds.
5. Sends the IR command.

If no power guard is configured, commands are sent directly.

## Code Table Format

The default code table is bundled at `custom_components/truma_saphir/truma_saphir_codes.csv` and is the supported code table for this repository. Forks can replace this CSV for other remotes, but upstream support is intentionally limited to the Truma Comfort RC code set.

The CSV file must contain these columns:

```csv
label,power,mode,temperature_c,fan,protocol,protocol_name,code2,source_code,confidence,notes
```

Required fields used by the integration:

- `power`: `on` or `off`
- `mode`: `Cooling`, `Heating`, `Automatic`, `Circulated air`, or `Off`
- `temperature_c`: integer temperature for cooling, heating, and automatic modes
- `fan`: `Low`, `Medium`, or `High` for cooling, heating, and circulated air modes
- `source_code`: MQTT payload sent to the IR bridge, for example `100,0xEBFFFFFFF0E217,56`

Rows with unsupported modes are ignored.

## Parameters

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | no | `Truma Comfort RC` | Entity name |
| `unique_id` | no | `truma_saphir_ir_climate` | Entity unique ID |
| `code_table` | no | bundled CSV | Optional path to another CSV code table |
| `send_topic` | no | `IRMINI1b50/send` | MQTT topic used by the IR bridge |
| `target_sensor` | no | `sensor.combined_indoor_temperature` | Current room temperature sensor |
| `initial_temperature` | no | `26` | Initial target temperature |
| `initial_fan_mode` | no | `high` | Initial fan mode |
| `send_repeats` | no | `2` | Number of times to publish each IR command |
| `repeat_delay` | no | `1.0` | Seconds between repeated publishes |
| `command_debounce` | no | `0.8` | Seconds to wait before sending after mode/temp/fan changes |
| `mqtt_qos` | no | `0` | MQTT QoS for command publish |
| `power_guard_entity` | no | `input_select.victron_mode` | Entity that represents upstream power readiness |
| `power_guard_on_state` | no | `开机` | State considered ready |
| `power_guard_on_service` | no | inferred | Service to call when power is not ready |
| `power_guard_on_service_data` | no | `{}` | Data for the power guard service call |
| `power_guard_delay` | no | `5.0` | Seconds to wait after enabling power |
| `external_thermostat` | no | `true` | Use Home Assistant sensor-based thermostat control |
| `external_operation_mode` | no | `cool` | Direction used by external thermostat `auto`: `cool` or `heat` |
| `external_idle_hvac_mode` | no | `fan_only` | Command sent after reaching target: `fan_only` or `off` |
| `cold_tolerance` | no | `1.0` | Lower tolerance around target temperature |
| `hot_tolerance` | no | `1.0` | Upper tolerance around target temperature |
| `min_cycle_duration` | no | `60.0` | Minimum seconds between compressor start/idle transitions |
| `cooling_temperature` | no | `16` | Truma temperature sent while externally cooling |
| `heating_temperature` | no | `31` | Truma temperature sent while externally heating |

## Known Limitations

- IR has no delivery acknowledgement. Repeat sending improves reliability but cannot prove that the air conditioner received the command.
- The entity is optimistic. It remembers the state it last sent.
- Other Truma models or remotes are outside the supported scope of this repository.
- Avoid frequent compressor mode changes. Let the appliance protect itself and observe the manufacturer's operating instructions.

## Installation

Copy `custom_components/truma_saphir` to your Home Assistant `/config/custom_components/` directory, then restart Home Assistant Core. Add the integration through the UI, or use the YAML example above.

## License

MIT
