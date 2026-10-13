---
title: "SelfLore · 项目维护卡"
project: "selflore"
updated: "2026-10-12"
status: "资料卡、图片、只读诊断与联合恢复已隔离验证；日常待0005迁移及媒体配置，生产未操作"
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

本机日常使用已固定：首次在项目根运行`.\start-local.cmd -Configure`隐藏输入app角色密码，此后运行`.\start-local.cmd`，访问`http://127.0.0.1:24566`，Ctrl+C停止。启动自动加载`apps/api/.env`、只读检查开发库、冻结依赖与构建页面；不会迁移数据库。`.env`不含密码，凭据单独保存在仅当前用户和SYSTEM可读取的忽略缓存目录。`-CheckOnly`可诊断；2026-10-09用户配置实际app密码后，只读连接检查及完整启动已通过，网页、健康检查、注册开关和未登录权限均核对正常。详见[固定启动说明](LOCAL_START.md)。

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

更新前可在项目根执行`.\backup-db.cmd`生成带时间戳的完整开发库备份；`.\backup-db.cmd -Rehearse`会恢复到新建密码保护的6179私有实例，核对一致后停止。备份固定保留在受限权限、Git忽略的`backups/database`，迁移凭据与app启动配置独立。2026-10-09真实空开发库恢复及隔离有数据补充演练均通过；详情见[备份与恢复说明](DATABASE_BACKUP.md)。

本机 `deploy\publish.cmd -CheckOnly` 从指定 Git 提交的原始字节进行隔离测试和构建，不连接服务器。检查、包清单、源码与工具摘要保存在 Git 忽略的 `local-deployment/releases/<release-id>`；临时缓存另存。失败、跳过必要测试、调试工作区或测试仓库产物均不可发布。后续阶段必须使用同一已验证发布 ID，不重新构建。完整说明在本机 `deploy/README.md`。

Linux发布遵循 **暂存 → 管理员一致备份 → 指定发布包迁移 → 激活** 流程。迁移使用服务器受保护凭据，无需PTY；持久状态支持查询与中断恢复。激活核对真实进程、前端版本、数据库与入口readiness；仅已证明兼容的版本允许自动回退，其余保留状态并要求人工处理。共享图片及数据库不随版本目录替换，不执行down SQL。本次仅完成本地验收，未连接生产；当前提交的浏览器测试定位器问题仍阻止晋级，工作区已有修复尚未提交。

## 出问题先做什么

- 页面 404：确认 `apps/web/dist/index.html` 已构建，随后重启 API。
- 登录 / 503：检查 app 角色 DSN、目标端口和完整迁移状态；开发默认允许 24566 / 24567 Origin。
- 保存 409：服务端版本已变化，编辑器保留输入。查看最新版本后合并再保存，勿重复覆盖。
- 迁移报历史变动：恢复原 SQL 字节，不修改数据库历史。失败版本的 DDL、授权与账本同事务回滚。
- 本地日志看终端；服务器日志 `journalctl -u selflore-api.service`，当前路径 `readlink -f /srv/selflore/current`。
- 保留 PostgreSQL 数据与正式迁移前备份。回收站可恢复卡片、合集和原有关系；没有永久删除接口。

接口说明见 [WORKSPACE_API.md](apps/api/WORKSPACE_API.md)。已有验收记录：完整隔离后端61项、原四页浏览器4项通过；后续前端23项与新增中央新建2项触控验收通过。移动底栏为知识／观点／新建／合集／我的，滚动固定和游客登录门槛已验证。详细运行记录与截图仅在本机保存，测试代码和复跑说明随仓库交付。

## 资料卡与图片（新增）

资料卡保存外部图片／摘录，说明与原材料分区，支持来源作者、发布者、平台和日期；可加入合集与引用，不进入复习。新增0005迁移、独立私有媒体／运维目录、鉴权图片接口和原图放大。Windows初始化、只读排查、联合备份恢复及Linux权限见 [图片维护说明](MEDIA_STORAGE.md)。

本次实现与验收使用一次性6179数据库和24568测试服务；日常6171未追加本次迁移，生产未操作。启用前先备份、追加迁移、显式ConfigureMedia并设置媒体环境变量，再重启。检查用`check-media.cmd`，默认只读；记录容量用`-Record`，hash排查用`-Deep`。新库完整备份为v2数据库＋图片，旧无附件v1兼容。已有资料后不可自动回退两类旧程序。
