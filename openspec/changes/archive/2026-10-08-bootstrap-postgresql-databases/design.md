## Context

见 `proposal.md`。API 已使用 uv 管理 Python 3.13，但尚无数据库依赖、迁移工具或数据库连接代码。开发环境为 Windows，生产环境为 Linux 上的 PostgreSQL 18；两个实例相互独立。当前需求仅是首次初始化，不部署服务或复制数据。

## Goals / Non-Goals

**Goals:** 使用同一跨平台命令初始化 dev/prod；将生产角色与对象限制在对应环境；首次执行与安全重入均可验证。

**Non-Goals:** 不在每次发布时建库、不接入 HTTP 请求路径、不复制生产数据、不删除已有对象、不管理 PostgreSQL 服务安装或网络暴露。

## Decisions

### Python CLI 与连接参数

在 `apps/api/` 新增 Python 模块，使用现有 uv 环境与 psycopg 3 连接 PostgreSQL。要求 `--env`、`--host`、`--port`、`--admin-user`，可选隐藏输入管理员密码的开关；不接受包含密码的命令行参数。显式主机避免 libpq 环境变量把命令指向另一实例。管理员认证可使用 libpq 的 peer、环境或密码文件机制，也可交互输入；首次创建登录角色的密码从专用环境变量或隐藏输入读取。选择 Python 而非平台 shell，以同一实现覆盖 Windows 与 Linux，并安全处理 SQL 标识符与秘密值。

### 环境专属名称与角色分离

数据库名为 `selflore_dev` / `selflore_prod`；角色名为 `selflore_<env>_owner`、`selflore_<env>_migrator`、`selflore_<env>_app`。owner 为 `NOLOGIN`，数据库、`app` schema 和测试表均由 owner 持有。migrator 仅具有对 owner 的 `SET ROLE` 能力，不自动继承；app 只获数据库 CONNECT、schema USAGE、测试表 SELECT。环境后缀使两环境即使误处同一 PostgreSQL 实例也不共享凭据或角色。

### 创建顺序与幂等行为

先验证管理员连接与目标版本，再检查现有对象。不存在时创建角色、数据库、schema 与表；`CREATE DATABASE` 在自动提交连接执行。现有对象逐项核对所有者、结构和角色关键属性；不修复冲突或重置已有角色密码。测试表 `app.connection_probe` 仅含整型主键且为空。创建表前在同一会话执行 `SET ROLE owner`，确保所有权；完成后恢复角色。对象权限显式授予，撤销数据库对 PUBLIC 的默认访问和 public schema 的 CREATE。失败时报告已完成步骤以便重跑，不假装跨数据库操作可原子回滚。

PostgreSQL 18 会在 `pg_constraint` 中单独记录列的 `NOT NULL` 约束。核对测试表时，以 `pg_attribute.attnotnull` 验证非空性，并只对其他约束要求恰好有一条作用于 `id` 的非延迟主键；这样可接受首次运行已创建、但在授权前中断的表，同时仍拒绝额外业务约束。

### 后续迁移边界

这个命令只处理首次引导和测试表，不充当通用 schema 迁移框架。未来业务表使用独立的版本化迁移流程，同样通过 migrator 登录并切换到 owner；各环境独立记录迁移进度。

### 本地执行记录

文档记录用户已在 Windows 本机的 `127.0.0.1:6171` 成功初始化 `dev`，不记录任何密码。部署 SSH 接入属于独立变更，不在数据库初始化文档中说明。

## Risks / Trade-offs

- [管理员权限过宽] → 命令仅作首次引导；运行身份需有创建角色和数据库及分配所有权的能力，应用不使用管理员凭据。
- [连接到错误实例] → 端口必填、输出目标主机和环境名称，生产前按文档核对实例。
- [途中失败留下部分对象] → 创建步骤可重复，现有对象必须验证；不会执行 DROP 或覆盖。
- [同名角色已属于其他项目] → 环境专属命名及冲突校验，拒绝自动接管。
- [代理工作区未直接连接实际 PostgreSQL] → 用模拟连接覆盖关键行为；用户已在 Windows 本机的 PostgreSQL 18 实例完成 `dev` 初始化，生产实例尚待独立验证。

## Migration Plan

1. 在 dev 实例运行初始化命令，核对角色、所有权、权限与空测试表。
2. 在 CI 的临时 PostgreSQL 18 实例运行同一命令和检查。
3. 在生产实例以管理员身份运行 `--env prod`，使用生产专属密码，核对结果后交给后续部署流程。
4. 本变更不修改已有数据库；若需撤销新建对象，应先人工盘点后单独处理。
