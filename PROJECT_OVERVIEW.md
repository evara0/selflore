# SelfLore

## 项目目标

SelfLore 是一个正在重建的个人知识与记录空间。当前版本建立了可运行的前后端技术基线与视觉布局框架：后端提供最小健康检查，前端提供带网格背景、玻璃主内容区和响应式底部导航的导航壳层。业务数据、认证、数据库和正式内容将在后续独立变更中实现。

## 技术栈

| 区域 | 技术 |
| --- | --- |
| 后端 | Python 3.13、FastAPI、Uvicorn、uv、pytest |
| 前端 | React、TypeScript、Vite、pnpm、CSS |
| API 本地端口 | `24566`，`GET /api/health` |
| Web 本地端口 | `24567` |
| 规格与流程 | OpenSpec、Git |

## 本地启动

```powershell
cd apps/api
uv sync --frozen
uv run uvicorn app.main:app --host 127.0.0.1 --port 24566
```

```powershell
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

## 当前边界

当前项目不包含数据库、账号认证、业务 API、数据迁移或正式知识内容。
