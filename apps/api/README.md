# SelfLore API

要通过后端端口访问前端页面，先在项目根目录构建前端：

```text
cd apps/web
pnpm install --frozen-lockfile
pnpm build
```

然后启动后端，无需启动 Vite 开发服务：

```text
cd ../api
uv sync --frozen
uv run uvicorn app.main:app --host 127.0.0.1 --port 24566
```

页面地址：`http://127.0.0.1:24566/`。健康检查地址：`http://127.0.0.1:24566/api/health`。

如果在后端已启动后才构建前端，需重启后端才能挂载新的构建目录。前端未构建时，健康检查仍可使用，页面请求返回 404。

启动前配置 SELFLORE_DATABASE_URL 为 app 角色 DSN，并显式执行 `migrations/` 的完整增量链；不能用应用启动代替迁移。

业务实现位于 `app/routers`、`schemas`、`services`、`repositories`；支持知识 / 观点卡片、稳定链接、混合合集、FSRS 调度、个人资料和学习足迹，复用已有认证。

- [工作区 API](WORKSPACE_API.md)
- [增量建表与迁移](CARD_MIGRATIONS.md)
- [隔离数据库与浏览器测试](WORKSPACE_TESTING.md)
- [数据库首次初始化](DATABASE_SETUP.md)
- [账号与安全配置](AUTH_CONFIGURATION.md)
- [日常维护](../../MAINTENANCE.md)
