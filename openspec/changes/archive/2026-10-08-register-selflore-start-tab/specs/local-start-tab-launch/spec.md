## Purpose

使本机 Start Tab 能独立启动和识别 SelfLore 的 API 与 Web 开发服务，并提供依赖顺序明确的一键启动入口和对应的本机访问地址。

## ADDED Requirements

### Requirement: Start Tab 可启动 SelfLore API
Start Tab SHALL 提供 SelfLore API 启动项，使用项目本地环境在 127.0.0.1:24566 运行，并通过健康检查识别状态。

#### Scenario: 启动 API
- **WHEN** 用户在 Start Tab 启动 SelfLore API 且端口可用
- **THEN** API 在 24566 端口监听，`/api/health` 可访问，Start Tab 显示运行状态

### Requirement: Start Tab 可启动 SelfLore Web
Start Tab SHALL 提供 SelfLore Web 启动项，在 127.0.0.1:24567 运行，并通过端口识别状态及提供打开页面的入口。

#### Scenario: 启动 Web
- **WHEN** 用户在 Start Tab 启动 SelfLore Web 且端口可用
- **THEN** Web 在 24567 端口监听，Start Tab 可打开本机页面

### Requirement: 一键启动顺序
Start Tab SHALL 提供 SelfLore 组合启动入口，并在启动 Web 前启动 API。

#### Scenario: 启动组合
- **WHEN** 用户启动 SelfLore 组合
- **THEN** Start Tab 先启动 API，再启动 Web
