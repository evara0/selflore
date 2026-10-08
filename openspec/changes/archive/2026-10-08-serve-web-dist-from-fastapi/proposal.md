## Why

当前 FastAPI 只提供 `/api/health`，即使前端已构建，单独启动后端也无法通过后端端口打开页面。需要让本地与后续部署能够直接使用前端构建产物，而无需运行 Vite 开发服务。

## What Changes

- FastAPI 在前端 `dist` 存在时提供首页、构建资源和前端页面路由。
- 保留 `/api/*` 为 API 空间；未知 API 路径和不存在的静态资源返回 404，不回退到前端首页。
- 前端尚未构建时，后端仍可独立启动并提供现有健康检查。
- 增加覆盖页面、资源、前端路由及 API 边界的验证。

## Capabilities

### New Capabilities

- `web-dist-serving`: 后端端口直接提供已构建的前端应用。

### Modified Capabilities

- 无。

## Impact

修改 `apps/api/` 中的应用路由与测试；读取 `apps/web/dist/`，不改变前端开发服务器配置，也不引入数据库、认证或部署服务。
