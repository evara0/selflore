# api-health-service Specification

## Purpose

为 SelfLore 建立最小且可自动验证的 HTTP 服务入口，让开发者和后续交付流程能在不依赖业务功能、数据库或外部服务的情况下确认 API 进程已成功启动。

## Requirements

### Requirement: 健康检查端点

服务 SHALL 提供无需认证的 `GET /api/health` 端点。健康检查成功时，该端点 MUST 返回 HTTP `200 OK`，并以 JSON 响应体精确表示 `{"ok": true}`。

#### Scenario: 服务正常运行

- **WHEN** API 进程已启动且客户端向 `GET /api/health` 发送请求
- **THEN** 服务 SHALL 返回 `200 OK` 和 JSON 响应 `{"ok": true}`

### Requirement: 固定本地监听端口

项目提供的开发启动方式 MUST 使 API 服务监听本机端口 `24566`，以便健康检查可通过该固定端口访问。

#### Scenario: 使用项目启动方式

- **WHEN** 开发者按项目说明启动 API 服务
- **THEN** `GET http://127.0.0.1:24566/api/health` SHALL 返回成功的健康检查响应

### Requirement: 最小服务边界

健康检查 MUST 独立于后续业务端点，MUST NOT 要求数据库、认证配置、环境秘密或外部服务才能返回成功响应。后续增加业务端点 SHALL 不改变健康检查的无状态存活语义。

#### Scenario: 无业务基础设施运行

- **WHEN** 未配置数据库、认证或外部服务
- **THEN** API 服务 SHALL 仍能启动并返回成功的健康检查响应
