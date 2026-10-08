# 认证配置与首位管理员

本说明描述现有API的通用配置，不包含真实凭据或服务器接入信息。先按 [数据库初始化](DATABASE_SETUP.md) 创建目标环境并执行完整迁移链；以下命令均在 `apps/api/` 执行。

## 1. API环境变量

| 变量 | 用途与默认行为 |
| --- | --- |
| SELFLORE_DATABASE_URL | psycopg连接DSN，必须使用所选环境的app角色；缺失时数据库操作返回503，健康检查仍可用 |
| SELFLORE_ENV | dev或prod，默认dev |
| SELFLORE_ALLOWED_ORIGINS | 允许的完整Origin，多个地址用逗号分隔；dev默认允许本机API24566和Vite24567 |
| SELFLORE_ALLOW_REGISTRATION | 默认true，显式false关闭公开注册 |
| SELFLORE_THROTTLE_KEY | 登录限速桶HMAC密钥；prod必须由部署者注入独立随机值 |
| SELFLORE_ALLOW_INSECURE_HTTP | prod受限临时HTTP测试开关，默认false |

配置由进程环境读取；修改后重启后端。数据库密码、限速密钥、会话与CSRF值不得提交或写入前端存储。DSN可不含密码，并通过libpq密码文件提供凭据。

## 2. 开发运行示例

示例端口5432应替换为目标数据库端口；先在本机配置app角色的libpq密码文件，然后在PowerShell执行：

```powershell
uv sync --frozen
$env:SELFLORE_ENV = 'dev'
$env:SELFLORE_DATABASE_URL = 'host=127.0.0.1 port=5432 dbname=selflore_dev user=selflore_dev_app'
uv run uvicorn app.main:app --host 127.0.0.1 --port 24566
```

开发默认Origin为 `http://127.0.0.1:24566` 和 `http://127.0.0.1:24567`。若使用其他浏览器入口，显式设置SELFLORE_ALLOWED_ORIGINS，不能省略端口或混用不同主机名称。

公开注册只创建普通用户和默认资料，成功后需要登录。用户名为3–32字符，以英文字母开头，后续可包含字母、数字、下划线或连字符，按大小写不敏感保持唯一。注册或修改密码要求12–128字符。`GET /api/auth/config` 返回registration_enabled，关闭注册时前端隐藏入口，注册请求返回403。

## 3. 首位管理员

由有migrator凭据的操作人员在交互终端执行，数据库密码按 [数据库初始化](DATABASE_SETUP.md) 的安全方式预先配置：

```powershell
uv run python -m app.admin_bootstrap --env dev --host 127.0.0.1 --port 5432 --username admin_user
```

命令隐藏输入并确认管理员账号密码；数据库中已有管理员时拒绝再次初始化，即使该管理员已停用。生产环境显式选择prod及经核对的主机、端口。应用运行账号不执行管理员初始化，首个公开注册用户不会自动成为管理员。

## 4. 生产Origin与Cookie

正常prod配置必须提供HTTPS Origin和SELFLORE_THROTTLE_KEY。会话Cookie使用 `__Host-selflore_session`，启用Secure和HttpOnly，并限制跨站发送；状态变更检查Origin，已登录请求还需X-CSRF-Token。

只有受限临时HTTP测试显式设置SELFLORE_ALLOW_INSECURE_HTTP=true后，prod才接受所配置的HTTP Origin，并使用独立的 `selflore_session_http` Cookie。HTTP模式不设置Secure，凭据和会话会明文传输，应仅使用受限访问和测试凭据。切换回HTTPS时关闭临时开关、配置HTTPS Origin并重启，浏览器重新登录。

具体域名、密钥值、代理和发布接入仅在部署环境管理；本仓库提供通用配置说明，具体部署步骤仅在本机资料中维护。

## 5. 验证

- `GET /api/health` 应返回200和 `{"ok":true}`。
- `GET /api/auth/config` 应反映注册开关；未登录访问 `/api/auth/me` 应返回401。
- 通过页面注册普通账号、登录、刷新恢复会话、退出；退出后受保护请求不可继续使用原会话。
- 改密会撤销该账号原有会话；普通用户管理请求应返回403，管理员停用账号后其会话失效。

前端、离线和隔离数据库测试步骤见 [本地验证](WORKSPACE_TESTING.md)。本机历史验收资料不作为新环境运行前提。
