## Context

见 `proposal.md`。目前 `apps/api/app/main.py` 只有健康检查及静态页面服务，使用 FastAPI、psycopg 与 PostgreSQL 18；`apps/web/src/App.tsx` 的用户名／密码弹窗只显示“尚未接入”。`app` schema 已由 `db_bootstrap.py` 创建，数据库角色分为不可登录的 owner、可切换 owner 的 migrator、无 DDL 权限的 app。当前没有 ORM、迁移框架或业务表。与本变更并行的账号弹窗 change 尚未归档，实施时应在其现有 UI 上接入请求。

## Goals / Non-Goals

**Goals:**

- 在现有单体 API 与同源前端中建立可撤销的账号会话，并把普通用户／管理员权限放在服务端判定。
- 用 PostgreSQL 版本迁移建立可重复升级的身份数据结构，保留现有 bootstrap 的角色隔离。
- 给未来个人内容表留下稳定的 `users.id` 外键目标。

**Non-Goals:**

- 本轮不做邮箱验证、找回密码、OAuth、MFA、组织／团队权限及内容表迁移。
- 不让公开注册创建管理员，也不自动把首位注册用户设为管理员。
- 不通过应用启动过程自动执行生产迁移，不自动清理或回滚账号数据。

## Decisions

### 用户名与账号模型

沿用现有 UI 的用户名＋密码形式，不引入邮箱依赖。用户名在 API 入口转为小写，规则为 3–32 位 ASCII 字母、数字、下划线或连字符，首位为字母；数据库用规范化值的唯一约束兜底。密码允许 12–128 个字符，不裁剪空格，不规定字符组合；以 Argon2id 哈希存储，参数至少达到 OWASP 当前基线，并通过压测调节。公开注册由部署配置控制，关闭时前端隐藏注册标签。空账号库中的首个管理员由仅部署人员可运行的 CLI 创建；CLI 在事务中检查尚无管理员，隐藏输入密码并使用 migrator 凭据。管理员创建其他账号时提供初始密码；此流程不提供邮件发送。

账号状态仅有可用／停用两种，因此列名为肯定语义的 `is_active boolean NOT NULL DEFAULT true`。角色使用 `member`、`admin` 两值约束，不将多个权限布尔值散落在用户表。管理员改变角色／可用状态时，在事务中串行化相关操作，检查变更后仍至少有一个可用管理员，并撤销目标账号的会话。相比用“第一个注册用户即管理员”或客户端角色声明，此方式避免公开入口提权。

### 服务端会话与浏览器保护

成功登录生成至少 256 位随机会话密钥，只把密钥的 SHA-256 摘要存入数据库；原值仅存在 Cookie 中。会话采用 24 小时绝对有效期，不做自动续期；登出、改密、停用或改角色均写入 `revoked_at`。每次受保护请求检查会话、过期时间及当前用户状态／角色。生产 Cookie 名为 `__Host-selflore_session`，设置 `Secure`、`HttpOnly`、`SameSite=Lax`、`Path=/`，不设置 `Domain`；仅本机 HTTP 开发模式使用非 `__Host-` 名称和非 Secure Cookie。前端不把密钥或身份状态持久化到 Web Storage。

对所有非安全 HTTP 方法验证请求 `Origin` 与配置的同源地址；登录／注册也执行该检查。会话表保存独立随机 CSRF 值，`GET /api/auth/me` 向同源前端返回它；已认证的状态变更请求必须把它放入自定义请求头。服务端比较时使用恒定时间比较。`SameSite` 是附加防线，不能替代 CSRF 校验。API 不开放带凭据的跨源 CORS；生产按同源部署。登录按来源 IP 与规范化用户名两个维度限速，计数写入数据库以跨进程生效；错误文案统一，未找到用户时执行相同成本的虚拟密码校验。

选用可撤销的数据库会话而非浏览器存储 JWT，因为管理员停用与改密需要立即生效。选用数据库中的限速记录而非进程内计数，以适应多 worker；不增加 Redis 服务。

### API 与授权边界

初始接口为 `POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`、`POST /api/auth/logout`、`POST /api/auth/change-password`；管理员接口为 `GET /api/admin/users`、`POST /api/admin/users`、`PATCH /api/admin/users/{id}`。`GET /api/auth/me` 返回账号 ID、用户名、角色、可用状态及 CSRF 值；其他公共响应不暴露密码哈希、会话摘要或内部限速信息。注册后不自动登录，以免混合注册与会话建立的 CSRF 边界。`PATCH` 只接受角色或可用状态字段，并记录操作者与目标；账号不做硬删除。

后端共享认证依赖返回当前数据库账号；普通用户本人接口从会话获取目标 ID，管理员依赖另行检查角色。无会话返回 401，有会话但权限不足返回 403。当前项目尚无内容资源；未来内容 API 必须同时按 `owner_user_id` 限定对象访问，而非只检查是否登录。前端从 `/api/auth/me` 恢复状态，登录／注册弹窗呈现服务端错误，登录后显示账号与退出入口；管理员列表可另建最小管理视图。

### 迁移文件与数据结构

采用 `apps/api/migrations/0001_identity.sql` 和小型 psycopg 迁移命令，避免在尚无 ORM 的项目中引入只为首批表服务的 ORM。迁移命令显式选择 `dev` 或 `prod`，核对目标数据库名，持有事务级 advisory lock，以 migrator 连接并显式切换 owner；每个版本在单个事务中执行 SQL、写入 SHA-256 校验值与提交。迁移历史表仅 owner 可访问，app 角色不得读取。历史文件一经执行不可修改；后续结构变化新增编号文件。`0001` 在现有 `app` schema 中建立：

| 表 | 关键列与约束 | 索引／访问 |
| --- | --- | --- |
| `app.schema_migrations` | `version text PRIMARY KEY`、`checksum_sha256 char(64) NOT NULL`、`applied_at timestamptz NOT NULL` | 仅 owner 访问 |
| `app.users` | `id uuid PRIMARY KEY`、`username varchar(32) NOT NULL UNIQUE`、`password_hash text NOT NULL`、`role text NOT NULL CHECK (role IN ('member','admin'))`、`is_active boolean NOT NULL DEFAULT true`、`created_at`／`updated_at timestamptz NOT NULL`；用户名格式及小写约束 | `username` 唯一索引；app 仅 SELECT／INSERT／UPDATE |
| `app.auth_sessions` | `id uuid PRIMARY KEY`、`user_id uuid NOT NULL REFERENCES app.users(id)`、`token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash)=32)`、`csrf_token text NOT NULL`、`created_at`／`expires_at timestamptz NOT NULL`、`revoked_at timestamptz NULL`；`expires_at > created_at` | `(user_id, expires_at)` 与未撤销会话索引；app 仅 SELECT／INSERT／UPDATE |
| `app.auth_login_throttle` | `bucket_key char(64) PRIMARY KEY`、`failed_count integer NOT NULL CHECK (failed_count >= 0)`、`window_started_at`／`blocked_until`／`updated_at timestamptz` | 定时清理使用 `updated_at` 索引；app 仅 SELECT／INSERT／UPDATE／DELETE |
| `app.account_audit` | `id uuid PRIMARY KEY`、`actor_user_id uuid NULL REFERENCES app.users(id)`、`target_user_id uuid NOT NULL REFERENCES app.users(id)`、`action text NOT NULL`、`created_at timestamptz NOT NULL`，角色／状态变化的前后值列 | `(target_user_id, created_at)`；app 仅 INSERT，管理员读取需后续显式授权与接口 |

UUID 由 API／管理命令生成，无需数据库扩展。`auth_login_throttle.bucket_key` 使用部署密钥对限速维度做 HMAC，避免保存原始 IP；密钥由运行环境注入，不写入仓库。`account_audit` 不存密码或令牌。布尔列 `is_active` 在 SQL、Python 模型和 API 中保持同一肯定含义；停用时间如将来需要再加独立时间戳。迁移末尾只给 app 角色授予上表所列 DML，不授予 DDL、owner 成员关系或迁移表权限。

## Risks / Trade-offs

- [公开用户名注册可能被滥用] → 注册与登录均限速；部署时可由配置关闭公开注册，管理员创建仍可用。
- [Cookie 会话依赖同源与 HTTPS] → 生产通过现有站点入口提供 HTTPS，同源校验使用明确配置；本机 HTTP 例外只能在开发模式启用。
- [管理员并发停用／降级导致无人可管理] → 相关事务使用同一数据库锁并在锁内检查可用管理员数量。
- [账号表含密码哈希且 app 角色需读取以验证] → 不向 API 返回该列，不写入普通日志；数据库备份及凭据按现有部署边界保护。
- [迁移失败或旧文件被改动] → 单版本事务回滚，校验值拒绝静默漂移；修复通过新迁移完成。

## Migration Plan

1. 先在开发库运行 `0001_identity.sql`，检查表、约束、索引、owner 与 app 角色权限；重复运行应只验证并跳过。迁移测试使用独立临时库或事务化数据库夹具，不触碰现有账号数据。
2. 部署后端与前端时先保持注册入口为受控配置；迁移完成并通过认证／鉴权验证后开放注册。空库先通过 CLI 创建管理员，再验证普通用户注册不能取得管理员角色。
3. 生产发布前备份目标库，使用 prod migrator 明确执行迁移，再部署兼容新结构的 API／Web。失败时停止发布并依赖事务回滚；代码需要回退时恢复兼容旧接口的构建。若必须撤回已提交的结构，先评估数据并编写新的前向迁移或从备份恢复，不自动执行破坏性 down 脚本。

## References

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)：密码哈希选择与 Argon2id 基线。
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)：随机会话标识、Cookie 属性与服务端失效。
- [OWASP Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)：CSRF 令牌及 SameSite 的适用边界。
