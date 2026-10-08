# web-dist-serving Specification

## Purpose

使已构建的 SelfLore 前端能够通过 FastAPI 的同一端口访问，同时保持 API 路径与静态资源的错误语义，支持无需前端开发服务器的运行方式。

## Requirements

### Requirement: 后端提供前端构建内容

当前端构建产物在后端启动时存在，后端 SHALL 在根路径提供前端首页，并 SHALL 提供构建产物中的静态文件，不要求前端开发服务器运行。

#### Scenario: 打开首页与静态资源

- **WHEN** 前端已构建，客户端通过后端端口请求 `/` 和首页引用的静态资源
- **THEN** 两类请求 SHALL 返回相应的构建内容与成功状态

### Requirement: 前端页面路由回退

对于非 API、非静态资源的页面路径，后端 SHALL 返回前端首页，使客户端路由能够接管页面。

#### Scenario: 直接访问前端页面

- **WHEN** 前端已构建，客户端直接请求 `/journal` 等页面路径
- **THEN** 后端 SHALL 返回前端首页，而不是 404

### Requirement: API 与资源边界

前端挂载 SHALL 保留现有 API 响应；未知 `/api/*` 路径和不存在的静态资源 MUST 返回 404，不得返回前端首页。静态文件服务 MUST 限制在构建产物目录内。

#### Scenario: 健康检查仍可访问

- **WHEN** 客户端请求 `/api/health`
- **THEN** 后端 SHALL 返回现有的成功响应

#### Scenario: 未知 API 与缺失资源

- **WHEN** 客户端请求不存在的 `/api/missing` 或 `/assets/missing.js`
- **THEN** 后端 SHALL 对各请求返回 404

### Requirement: 无构建产物时仍可运行 API

当前端构建产物不存在时，后端 SHALL 正常启动并提供已定义的 API；首页 SHALL 返回 404。

#### Scenario: 尚未构建前端

- **WHEN** 前端构建产物不存在且后端启动
- **THEN** `/api/health` SHALL 可用，`/` SHALL 返回 404
