# 数据库初始化与迁移

本说明随仓库交付，适用于新环境和已有环境。需要已运行的PostgreSQL 18；应用不会安装数据库或在启动时自动建表。以下命令在 `apps/api/` 执行，示例使用本机回环地址和5432端口，请替换为实际目标。

## 1. 同步依赖与准备凭据

```powershell
uv sync --frozen
uv run python -m app.db_bootstrap --help
uv run python -m app.db_migrate --help
```

首次初始化需要能创建数据库、角色和分配所有权的PostgreSQL管理员。管理员密码可通过libpq密码文件、操作系统认证或 `--prompt-admin-password` 隐藏输入。首次创建migrator和app角色时，命令会分别隐藏输入并确认密码；非交互环境可安全注入 `SELFLORE_MIGRATOR_PASSWORD` 和 `SELFLORE_APP_PASSWORD`。

迁移命令从 `SELFLORE_MIGRATOR_PASSWORD` 或libpq密码文件获取migrator凭据，不会交互提示该数据库密码。运行前应先配置凭据。密码文件和环境变量实际值仅在本机或部署环境管理，不写入仓库、文档或命令参数。

## 2. 首次初始化

仅当目标环境尚未准备好时执行：

```powershell
uv run python -m app.db_bootstrap --env dev --host 127.0.0.1 --port 5432 --admin-user postgres --prompt-admin-password
```

`postgres` 为示例管理员角色，可替换为具备所需权限的实际角色。命令显式选择dev或prod；目标名称如下：

| 环境 | 数据库 | owner | migrator | app |
| --- | --- | --- | --- | --- |
| dev | selflore_dev | selflore_dev_owner | selflore_dev_migrator | selflore_dev_app |
| prod | selflore_prod | selflore_prod_owner | selflore_prod_migrator | selflore_prod_app |

owner不可登录并持有对象；migrator用于迁移且能显式切换owner；app用于运行API，不能创建或修改结构。首次初始化创建 `app` schema和只读验证表 `app.connection_probe`，业务表由后续迁移创建。

重跑会核对并复用已有对象，不清空记录、不重设已有密码；发现所有权、结构或权限冲突时停止。创建数据库无法与跨库操作放在同一事务中，首次失败可能留下已创建对象；核对原因后重跑，不以清空数据库处理失败。

## 3. 执行完整迁移链

配置migrator凭据后执行：

```powershell
uv run python -m app.db_migrate --env dev --host 127.0.0.1 --port 5432
```

当前链为0001身份、0002卡片工作区、0003知识复习。空库执行完整链；已有库只执行尚未完成版本。命令校验目标库、迁移角色、PostgreSQL主版本和历史SHA-256，在整次运行持有锁，每个版本的DDL、授权、回填及历史记录同事务提交。

历史SQL不可修改；新增结构使用新编号SQL。失败回滚当前版本，先修复原因再重跑，不直接改迁移账本，也不执行清空重建或破坏性down迁移。

生产初始化和迁移应显式选择 `--env prod` 及经核对的目标主机、端口，由有权限的操作人员在备份和隔离演练后执行。具体服务器接入及发布步骤仅在本机部署资料中维护，生产激活须等待同一发布包的迁移成功。

## 4. 验证与运行

再次运行相同迁移命令，应核对历史并跳过已完成版本。以app角色连接dev库验证最小权限：

```text
psql -h 127.0.0.1 -p 5432 -U selflore_dev_app -d selflore_dev -W
```

```sql
SELECT count(*) FROM app.connection_probe;
SELECT has_schema_privilege(current_user, 'app', 'CREATE') AS app_can_create;
```

验证表可读取，CREATE权限应为false。新初始化验证表没有插入记录。完整权限及升级演练见 [本地验证](WORKSPACE_TESTING.md)；运行API、首位管理员及认证环境变量见 [认证配置](AUTH_CONFIGURATION.md)，业务表说明见 [卡片迁移](CARD_MIGRATIONS.md)。
