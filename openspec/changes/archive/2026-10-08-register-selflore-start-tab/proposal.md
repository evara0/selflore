## Why

SelfLore 的 API 与 Web 开发服务目前需要分别在终端启动。将它们登记到 Start Tab 后，可以在本机通过同一入口查看状态并按顺序启动。

## What Changes

- 在 Start Tab 当前配置中登记 SelfLore API（24566）和 Web（24567）两个服务。
- 增加一键启动组合，使 Web 在 API 之后启动。
- 为服务配置端口状态检测和可打开的本机地址。

## Capabilities

### New Capabilities

- `local-start-tab-launch`: 从 Start Tab 启动并监测 SelfLore 的本地 API 与 Web 服务。

### Modified Capabilities

无。

## Impact

仅影响本机 `G:\start-tab\StartTabData\config.json` 和 SelfLore 的本地 OpenSpec 记录。API 端口 24566 与已有的“课笺”服务重合，因此两者不能同时占用该端口；不会改动该服务。
