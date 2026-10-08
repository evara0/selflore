## Why

SelfLore 即将接入 PostgreSQL，需要在 Windows 本机与 Linux 服务器上用同一方式初始化独立的开发库和生产库。手工复制 SQL 容易遗漏角色、所有权或授权，也容易把凭据写入仓库。

## What Changes

- 新增显式选择 `dev` 或 `prod` 的数据库初始化命令，接收目标 PostgreSQL 管理连接信息。
- 创建对应数据库、不可登录的 owner、迁移登录角色、应用登录角色、`app` schema 与一张无业务功能的测试表。
- 限制应用角色的权限，并使迁移操作以 owner 身份创建对象；重复执行时验证现有对象，不删除数据或重置已有密码。
- 文档说明首次初始化、凭据输入、跨平台运行与验证方法。

## Capabilities

### New Capabilities

- `postgresql-bootstrap`: 安全、可重复地初始化指定环境的数据库与最小角色/对象结构。

### Modified Capabilities

无。

## Impact

影响 `apps/api/` 的依赖、初始化脚本、测试和使用说明，以及目标 PostgreSQL 实例中的角色、数据库与表。不改变现有 HTTP API，也不自动连接或修改用户的实际数据库。
