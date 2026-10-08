# 卡片增量建表与迁移

用户确认的范围为：**现有数据库新建表，不清空数据**。本次保持 `0001_identity.sql` 原字节，沿用已有 SQL 迁移账本，增加两版：

| 版本 | 内容 |
| --- | --- |
| 0002_card_workspace | user_profiles、cards、topics、card_topics、tags、card_tags、card_links、collections、collection_items、activity_events；public.pg_trgm 和中文字面检索索引；回填老用户默认资料 |
| 0003_knowledge_review | review_units、review_states、review_logs；知识专属 FK、状态与评级约束、幂等请求键、到期索引 |

两版共13张新表，不删旧表、不清账号、不重置密码、不重写会话、不导入示例卡片。新库同样按0001→0002→0003运行；已有0001库只追加后两版。新增账号在注册 / 管理员创建同事务写入 profile。若应用回退期间旧版只插入了身份行，新版首次读取本人资料时补齐默认 profile，不覆盖已有资料。

早期重建设想提过 Alembic / ORM，但当前项目已采用 psycopg、不可变 SQL 文件、schema_migrations 和分阶段发布。此次延续实际机制，避免建立两套迁移历史。业务服务 / 请求模型 / SQL 仓储仍分层，未引入 ORM。

## 开发库执行

在 PowerShell 的 `G:\selflore\apps\api` 运行：

```powershell
uv sync --frozen
uv run python -m app.db_migrate --env dev --host 127.0.0.1 --port 6171
```

先通过本机安全凭据设施向进程提供 `SELFLORE_MIGRATOR_PASSWORD` 或 libpq 密码文件；不要把密码写入参数、聊天、Git 或日志。迁移角色必须为 selflore_dev_migrator，应用连接使用 selflore_dev_app；首次准备环境见 [数据库初始化](DATABASE_SETUP.md)。生产应显式选择prod并核对目标，先备份并演练，再通过同一发布包的迁移闸门执行，成功后才能激活；具体生产接入和部署步骤仅在本机维护。

执行前核对主机、端口、库名、PG18，并备份目标库。迁移全程持有 session advisory lock，先验证**全部**历史文件 SHA-256 与连续版本链；任何历史缺失或变动，在新 DDL 之前停止。每个版本的 DDL、资料回填、精确角色授权、账本插入同一事务；失败完整回滚该版本。再次运行跳过已执行版本。

app 角色仅得到明确版本清单的必要 DML：学习日志和活动仅 SELECT/INSERT，不能 UPDATE/DELETE；不能 CREATE、TRUNCATE 或读取迁移账本。关系以 owner + id 复合 FK 保证数据库层隔离；知识最多一分类；合集成员位置为 deferred unique，可原子交换。

已安装的 pg_trgm 必须处于 public；若存在不同 namespace 的扩展则明确停止，不擅自移动。不可编辑已应用 SQL；后续变更增加新版本和对应 GRANTS。

## 验收范围

在工作区所属的一次性6179 PG18实例中验证了：空库全链、带账号与会话的0001增量升级、最终schema和权限一致、重复执行、并发迁移、篡改 / 缺失历史拒绝、DDL失败、授权失败回滚、13张表外键和 CHECK、资料回填、无演示内容。测试脚本仅允许显式隔离 DSN 和缓存数据目录。

2026-10-08：用户配置凭据后，对127.0.0.1:6171/selflore_dev完成实际迁移。该库原先只有app.connection_probe，故依次执行0001、0002、0003；原表行数及逐行摘要不变，13张业务表、profile回填条件、应用角色授权和public.pg_trgm已核对，重跑为空操作。未清空数据、未导入示例、未创建账号。

迁移前完整备份：`G:\selflore\.cache\backups\dev-before-card-migration-20261008-092330\selflore_dev.dump`，pg_restore --list读取成功；同目录verification.json记录目标、版本、备份SHA-256及原表摘要。缓存备份不纳入Git，请保留至验收完成。生产未连接。应用启动没有自动迁移。应用回退保留增量表与原身份表，不提供清空重建脚本或破坏性down迁移。
