# SelfLore API

FastAPI 后端，使用 psycopg 访问 PostgreSQL，业务入口为 `app.main:app`。产品说明见[项目首页](../../README.md)。

## 准备与运行

以下路径统一从仓库根定位，命令在 `apps/api` 执行：

```powershell
uv sync --frozen
```

1. 新环境按[数据库初始化](DATABASE_SETUP.md)准备 PostgreSQL、角色和完整迁移链；已有环境按[增量迁移](CARD_MIGRATIONS.md)升级。
2. 按[认证配置与手动运行](AUTH_CONFIGURATION.md)设置 app 角色连接、Origin 和凭据，再启动 API。固定 Windows 入口见[本地启动](../../LOCAL_START.md)。
3. 健康检查为 `http://127.0.0.1:24566/api/health`，交互式接口文档为 `/docs`。健康检查成功不代表数据库已配置或迁移完成。

API 可同时提供 `apps/web/dist` 中的页面。前端构建命令见[前端说明](../web/README.md#检查与构建)，构建完成后启动或重启 API；未构建时页面返回404，API仍可访问。应用启动不建表、不自动迁移，也不会自动读取 `.env`；环境加载方式见认证说明。

## 代码入口

| 路径 | 职责 |
| --- | --- |
| `app/main.py`、`app/auth.py` | 应用挂载、会话与权限 |
| `app/routers/`、`app/schemas/` | 业务路由与输入约束 |
| `app/services/`、`app/repositories/` | 业务逻辑、SQL及数据库访问辅助函数 |
| `app/db_bootstrap.py`、`app/db_migrate.py` | 数据库／角色准备与独立迁移 |
| `app/media_storage.py`、`app/media_diagnostics.py`、`app/db_backup.py` | 私有图片、诊断及备份恢复 |
| `migrations/`、`tests/` | 不可变SQL增量与后端测试 |

接口字段见[工作区 API](WORKSPACE_API.md)，测试命令与隔离约束见[本地验证](WORKSPACE_TESTING.md)，操作索引见[维护卡](../../MAINTENANCE.md)。
