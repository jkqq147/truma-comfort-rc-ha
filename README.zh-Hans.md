# Truma Comfort RC 红外空调 Home Assistant 集成

这是一个 Home Assistant 自定义 `climate` 集成，用于通过 MQTT 红外网关控制 Truma Comfort RC 空调。

集成默认内置一份 Truma Comfort RC 红外码表，并暴露一个标准空调实体。它适合“HA 发送 MQTT 到红外设备，再由红外设备遥控空调”的场景。

当前仓库只面向这一个型号/这份码表，参考手册见 [docs/truma-comfort-rc-manual-2018-06.pdf](docs/truma-comfort-rc-manual-2018-06.pdf)。它不是一个通用 Truma 空调框架。

## 功能

- 标准 Home Assistant `climate` 实体
- 支持 UI 配置流程和选项页
- 模式：`off`、`cool`、`heat`、`auto`、`fan_only`
- 默认启用 Home Assistant 外部温控
- 默认室温传感器：`sensor.combined_indoor_temperature`
- 默认 MQTT 发送主题：`IRMINI1b50/send`
- 默认上游供电检查实体：`input_select.victron_mode`
- 启动空调前可先确保逆变器或上游供电已开启
- 支持重复发送红外命令，提高红外链路可靠性
- 内置 CSV 红外码表，可直接替换为其他码表

## 安装

1. 将 `custom_components/truma_saphir` 复制到 Home Assistant 的 `/config/custom_components/`。
2. 重启 Home Assistant Core。
3. 进入“设置 -> 设备与服务 -> 添加集成”。
4. 搜索并添加 `Truma Comfort RC IR Climate`。
5. 保持默认值即可适配当前这套 MQTT 红外网关配置，也可以在选项页调整。

## 外部温控

外部温控默认开启。开启后，Home Assistant 的目标温度表示期望车内温度，而不是直接发送给 Truma 的目标温度。

前端使用 `auto` 模式运行。`auto` 背后的实际工作方向由 `external_operation_mode` 决定：

- `cool`：需要制冷时，底层发送 Truma 制冷 `16°C` 命令。
- `heat`：需要制热时，底层发送 Truma 制热 `31°C` 命令。

达到目标温度后，默认切到 `fan_only`，这样比直接关机再重启更平顺。也可以在选项页改成 `off`。

如果 Home Assistant 温度传感器变成 `unknown`、`unavailable`、不是数字，或者超过 `target_sensor_max_age` 没有更新，`auto` 会降级发送 Truma 原生 `Automatic` 红外码，温度使用 HA 当前目标温度。这样即使外部温控传感器链路异常，空调仍然可以启动。内置码表中的 Truma 原生 Automatic 没有风速维度。

默认温差逻辑：

- 制冷：高于目标温度 `1°C` 开始制冷，低于目标温度 `1°C` 进入空闲。
- 制热：低于目标温度 `1°C` 开始制热，高于目标温度 `1°C` 进入空闲。
- 压缩机最小切换间隔默认 `60` 秒。

## 供电保护

如果配置了供电实体，发送非关机命令前会先检查供电状态。

默认逻辑：

1. 检查 `input_select.victron_mode`。
2. 如果状态已经是 `开机`，直接发送红外命令。
3. 如果还没开机，先调用推断出的服务开启供电。
4. 等待 `5` 秒。
5. 再发送空调红外命令。

关机命令不会等待供电保护，会直接发送。

## 红外码表

默认码表位于：

```text
custom_components/truma_saphir/truma_saphir_codes.csv
```

当前仓库支持的是内置这份 Truma Comfort RC 码表。其他遥控器或其他 Truma 型号可以 fork 后替换 CSV，但不作为本仓库的默认支持范围。

## 测试

在仓库根目录运行：

```bash
python3 -m unittest tests/test_thermostat.py
```

## 许可

MIT
