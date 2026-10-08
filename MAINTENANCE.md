---
title: "SelfLore · 项目维护卡"
project: "selflore"
updated: "2026-10-08"
status: "本机实现、隔离 PostgreSQL 和浏览器已验证；6171 开发库已备份并完成0001–0003迁移，生产未操作"
environments:
  - "Windows 本地开发"
  - "Windows 隔离测试"
  - "Linux 发布流程（源码核实，未执行发布）"
---

# SelfLore · 项目维护卡

**改页面要构建，改后端要重启；数据库变更通过独立的增量迁移命令执行。**

SelfLore 用知识卡片帮助回忆，用观点卡片整理连接，支持混合合集翻阅和个人学习足迹。

## 项目是什么

| 部分 | 技术与位置 |
| --- | --- |
| 前端 | React / TypeScript / Vite；React Router、TanStack Query、安全 Markdown；`apps/web/src` |
| 后端 | Python 3.13 / FastAPI / psycopg；`apps/api/app`；沿用会话与 CSRF 认证 |
| 数据 | PostgreSQL 18，`app` schema；原身份表加 13 张卡片、组织、资料和学习表 |
| 依赖 | uv + `apps/api/uv.lock`；pnpm + `apps/web/pnpm-lock.yaml`；FSRS 普通调度，无 optimizer |
| 迁移 | `apps/api/migrations/0001–0003`；SQL 校验、全程 advisory lock、每版本事务和精确授权 |

## 各环境怎么运行

| 项目 | Windows 开发 | 一次性测试 | Linux 发布目标 |
| --- | --- | --- | --- |
| 目录 | `G:\selflore` | 同工作区 `.cache/card-tests` | `/srv/selflore/releases/<release-id>` |
| Web / API | Vite `24567` 代理 API `24566`；构建后 API 可同时提供页面 | 构建页面 + API `24568` | systemd `selflore-api.service`，默认 `127.0.0.1:24566` |
| PostgreSQL | `127.0.0.1:6171/selflore_dev` | `127.0.0.1:6179`，必须显式隔离标记 | `selflore_prod`、`6171`，按发布文档核对 |
| 配置 | 当前终端的 `SELFLORE_*` 环境变量 / libpq 凭据 | 显式测试 DSN，不复用开发库 | `/etc/selflore/api.env`，不随包上传 |

在 PowerShell 的 `G:\selflore\apps\api` 执行 `uv sync --frozen`。确认开发库及 migrator 凭据后，执行 `uv run python -m app.db_migrate --env dev --host 127.0.0.1 --port 6171`，只会应用未执行版本。首次数据库和角色初始化见 [数据库初始化](apps/api/DATABASE_SETUP.md)。

配置 `SELFLORE_DATABASE_URL` 为该库的 **app 角色** DSN，设置 `SELFLORE_ENV=dev`，执行 `uv run uvicorn app.main:app --host 127.0.0.1 --port 24566`。在另一终端 `G:\selflore\apps\web` 执行 `pnpm install --frozen-lockfile`、`pnpm dev`；访问 `http://127.0.0.1:24567`。终端 Ctrl+C 停止，再执行相同启动命令重启。账号和安全配置详见 [认证配置](apps/api/AUTH_CONFIGURATION.md)。

若只启动后端，先执行 `pnpm build`，再启动或重启 API；访问 `http://127.0.0.1:24566`。健康检查 `GET /api/health` 应为 `{"ok":true}`，登录后 `/api/me/profile` 可确认业务库连接。应用启动不建表、不运行迁移。

测试步骤与安全边界见 [WORKSPACE_TESTING.md](apps/api/WORKSPACE_TESTING.md)。本次使用隔离库和私有测试账号保存实际截图，未向开发库或生产库写入演示内容。

## 改什么，怎么生效

公开注册默认开启，无需手动设置开关；登录弹窗会显示注册标签。若需关闭，显式配置`SELFLORE_ALLOW_REGISTRATION=false`并重启后端；已有显式false会覆盖默认值，须移除或改为true。账号默认是普通用户，注册成功后再登录。

未登录时自动进入“演示空间 · 只读”：四页使用`apps/web/src/lib/demo.ts`的独立示例数据，不创建数据库账号。游客可搜索、查看关联、翻阅及揭示答案；新建、编辑、收藏、组织、设置和复习评分提示登录。登录后读取本人真实数据，退出或会话过期清理缓存并回到演示；资料及学习统计明确是样例。修改演示内容后按前端方式构建／刷新，无需数据库迁移。游客浏览、写入拦截和缓存隔离已通过组件及浏览器验收，详细记录与截图仅在本机保存；可复跑步骤见 [本地验证](apps/api/WORKSPACE_TESTING.md)。

| 修改 | 位置 | 生效方式 |
| --- | --- | --- |
| 知识、观点、合集、资料 | 页面中的编辑入口 | 保存即写当前环境数据库，相关查询缓存更新 |
| 页面与交互 | `apps/web/src/features`、`components`、`App.css` | 开发 Vite 热更新；发布需重新构建 |
| 业务与调度 | `apps/api/app/services`、`routers`、`schemas` | 后端重启；调度参数变动需另写状态升级方案 |
| 表结构 | 新增编号 SQL + `db_migrate.GRANTS` | 备份、隔离演练、人工迁移后再启用应用 |
| 依赖 | 两端清单与锁文件 | uv / pnpm 冻结同步，重新测试构建 |
| 配置 | 环境变量 / 运行配置 | 重启进程；生产 Origin 与 Cookie 模式需匹配入口 |

业务数据不会通过 Git 或发布包同步。发布包包含源码、迁移和前端构建产物；`.env`、虚拟环境、缓存和数据库不包含。主项目 `openspec/` 允许Git版本管理；`docs/`、`local-deployment/`、`deploy/`、本机部署步骤及原始初始化/认证操作记录被忽略。通用运行说明随仓库交付，本次不修改忽略规则。

## 更新程序

本机 `deploy\publish.cmd -CheckOnly` 验证依赖、测试、lint、构建并生成 `.cache/releases/<release-id>.tar.gz`，不连接服务器。包内必须包含同次构建产物和完整 0001–0003 SQL 链。

Linux发布遵循 **暂存 → 备份 → 指定发布包迁移 → 激活** 流程，具体接入和部署步骤仅在本机维护。新版本使用独立目录，`current` 切换并重启；探针失败尝试恢复原应用。增量表保留，应用回退不执行数据库 down / 清空操作。本次未连接生产或发布。

## 出问题先做什么

- 页面 404：确认 `apps/web/dist/index.html` 已构建，随后重启 API。
- 登录 / 503：检查 app 角色 DSN、目标端口和完整迁移状态；开发默认允许 24566 / 24567 Origin。
- 保存 409：服务端版本已变化，编辑器保留输入。查看最新版本后合并再保存，勿重复覆盖。
- 迁移报历史变动：恢复原 SQL 字节，不修改数据库历史。失败版本的 DDL、授权与账本同事务回滚。
- 本地日志看终端；服务器日志 `journalctl -u selflore-api.service`，当前路径 `readlink -f /srv/selflore/current`。
- 保留 PostgreSQL 数据与正式迁移前备份。回收站可恢复卡片、合集和原有关系；没有永久删除接口。

接口说明见 [WORKSPACE_API.md](apps/api/WORKSPACE_API.md)。已有验收记录：完整隔离后端61项、原四页浏览器4项通过；后续前端23项与新增中央新建2项触控验收通过。移动底栏为知识／观点／新建／合集／我的，滚动固定和游客登录门槛已验证。详细运行记录与截图仅在本机保存，测试代码和复跑说明随仓库交付。
