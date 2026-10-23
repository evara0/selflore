# 增量迁移与兼容性

本文负责已有环境升级、迁移版本及回退边界。首次创建数据库和角色见[数据库初始化](DATABASE_SETUP.md)。应用使用 psycopg、不可变SQL文件和 `app.schema_migrations`，启动不会自动执行迁移。

## 当前迁移链

以 `migrations/` 中编号文件为准，按顺序执行完整链；已有库仅追加未执行版本，不清空账号或内容。

| 版本 | 作用 |
| --- | --- |
| 0001_identity | 用户、会话、认证及迁移基线 |
| 0002_card_workspace | 卡片、个人资料、分类标签、稳定链接、合集与活动；public.pg_trgm及检索索引 |
| 0003_knowledge_review | 复习单元、FSRS状态和评分记录；约束、幂等请求及到期索引 |
| 0004_relax_username | 调整用户名约束，保留已有账号与数据 |
| 0005_reference_media | 资料卡、独立说明、来源字段、附件及卡片附件关系 |
| 0006_memo_cards | 备忘形式、稳定清单条目、条目关联及合并链接视图 |
| 0007_unified_card_tags | 账号内统一标签、旧ID映射及关系来源、名称规范化、30项约束与历史快照 |
| 0008_tabular_checklists | 清单三个固定文本字段槽位、列名、显示数量与附加值约束 |

新注册账号在事务中创建默认profile；缺少profile的旧账号由当前服务补齐，不覆盖已有资料。资料与备忘的输入约束见[API说明](WORKSPACE_API.md)。

## 升级已有开发库

1. 核对主机、端口、库名、PostgreSQL 18及迁移角色；先按[备份说明](../../DATABASE_BACKUP.md)备份并按需要演练。
2. 通过本机凭据设施配置 `SELFLORE_MIGRATOR_PASSWORD` 或libpq密码文件。迁移凭据不放进命令参数、Git或日志，不与app日常启动凭据混用。
3. 以下命令在仓库根的 `apps/api` 执行。6171是固定Windows开发入口的端口；其他环境替换为已核对的目标：

   ```powershell
   uv sync --frozen
   uv run python -m app.db_migrate --env dev --host 127.0.0.1 --port 6171
   ```

4. 再次运行应核对历史并显示无待执行版本。确认完成后重建前端并重启API；图片目录需另行按[媒体配置](../../MEDIA_STORAGE.md)准备。

迁移使用 `selflore_dev_migrator`；运行应用使用 `selflore_dev_app`。生产显式选择 `--env prod`，核对实际目标，并按同一候选包的备份、迁移、激活顺序执行；专用部署接入仅在维护者本机管理。

## 不可变历史与权限

- 迁移前校验全部历史文件SHA-256及连续版本前缀，全程持有session advisory lock；历史缺失、字节变动或链不连续时，在新DDL前停止。
- 每版DDL、授权、回填与账本同事务提交，失败只回滚该版；修复原因后重跑，不修改已应用SQL或手工改迁移账本。
- app角色仅获明确版本清单的必要权限，不能CREATE、TRUNCATE或读取迁移账本；owner持有对象，migrator用于升级。学习日志和活动只允许SELECT／INSERT。
- 关系使用owner与ID的复合外键保证隔离；排序等约束支持事务内重排。已安装pg_trgm必须处于public，发现其他命名空间时停止，不自动搬移扩展。
- 后续结构变更新增编号SQL并更新 `app.db_migrate.GRANTS`；不能重写已交付历史。

## 发布与回退

应用能力标记为 `reference-memo-tags-table-v1`，发布清单的 `features.memo` 必须与0006迁移一致。备忘增加的表和视图不会把原三类卡片转换成备忘；资料图片继续位于独立媒体目录。

只允许在能力标记、迁移清单和API等相关输入均已证明兼容时自动回退应用。缺少备忘或资料能力的旧包不可直接回退；数据库不执行反向SQL。探针失败后应保留真实状态，使用兼容版本修复，不伪造能力标记。

迁移及恢复的复跑方法见[本地验证](WORKSPACE_TESTING.md)。历史实例的表数、备份位置和验收结果不属于当前操作前提，已迁至[历史验收记录](../../openspec/changes/consolidate-public-operations-docs/historical-validation.md)。


## 统一标签升级与恢复（0007）

正式操作前先读[统一标签运行手册](TAG_MIGRATION.md)。迁移仅追加0007，不改0001至0006字节；标签名称扩为80字符，每卡最多30个，足以容纳原10主题加20标签。NFKC后去除Unicode首尾空白，同账号同名合并，大小写和内部空白仍有区别。账号之间绝不合并。

`topics/card_topics` 与 `legacy_tags/legacy_card_tags` 为升级快照；`tag_aliases` 保存每个旧ID、原名、原kind到规范ID的映射；`card_tag_sources` 保存有效来源，`card_tags` 为去重投影。迁移在排他锁和同一事务内重新生成映射、核验逐关系覆盖及30项上限；空名、超长或核验失败会回滚整个0007和授权／历史记录。旧表应用写权限撤销，应用通过兼容层操作新来源，不要求旧表持续双写。

应用启动和发布readiness要求新结构，不会自动迁移。发布包须声明 `features.unified_tags=true`，并包含0007；缺标记或与迁移清单不一致时拒绝。旧包只支持reference/memo时不得自动回退。采用同迁移清单、同features且满足既有API字节兼容门禁的包恢复，或前向修复；禁止反向压回单分类或删除映射。保留旧快照／映射，清理另立变更。

## 多字段清单升级

0008仅追加cards.memo_columns（固定三个列名）、memo_column_count（显示1–3列）及memo_items.extra_values（固定两个附加值）。第一列继续使用text，默认旧清单显示单列；ID、顺序、完成时间和关系不重建。减少列数只隐藏，名称和值保持；界面不提供永久删除字段。旧PATCH按同一行ID补回省略的extra_values，显式提交两个空字符串才清空附加值。新增行关联仅接受事实知识，已有其他类型关系可保留。

迁移前保留完整一致数据库备份，隔离恢复核对数据与结构签名，并核对清单三列与关联。恢复须使用原数据库owner及对应恢复role，不能以超级用户归属的扩展替代；不执行down SQL。readiness要求0008新增字段，旧版本不会理解附加字段，不能作为多字段清单的直接写入回滚目标；优先同能力包或前向修复，需要整库恢复时先明确备份后写入处理。当前功能尚未在日常或生产环境升级，维护者私有发布工具对新能力包的支持也未在本任务发布或验证。

## 卡片导入批次

0009_card_import_batches新增本人批次幂等记录，应用角色仅有SELECT／INSERT；旧卡片接口不变。先在隔离环境验证，再按既有备份与迁移流程操作。新增表可随应用回退保留，不删除已导入卡片及图片。
