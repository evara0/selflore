## Why

项目已有版本控制基线，但尚无可运行的服务入口。需要一个严格最小的 FastAPI 健康检查服务，以验证 Python 运行时、uv 依赖管理和 HTTP 服务启动方式，而不提前引入业务功能。

## What Changes

- 在 `apps/api/` 创建由 uv 管理的独立 Python 项目与锁定依赖。
- 提供一个仅用于服务存活确认的 `GET /api/health` 端点。
- 将开发服务固定监听到本机端口 `24566`。
- 添加覆盖健康检查成功响应的自动化测试和最小运行说明。
- 明确排除认证、数据库、业务路由、配置加载、Docker、CI/CD 和其他 API 功能。

## Capabilities

### New Capabilities

- `api-health-service`: 提供可通过固定 HTTP 健康检查端点确认服务可用性的最小 API 服务。

### Modified Capabilities

- 无。

## Impact

新增 `apps/api/` 中的 Python 项目文件、FastAPI 与 ASGI 服务器依赖、锁文件、测试及运行说明。服务将在本机端口 `24566` 暴露一个无状态公共健康检查端点；不会涉及数据、用户或外部系统。
