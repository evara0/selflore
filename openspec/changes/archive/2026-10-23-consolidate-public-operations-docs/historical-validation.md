# 从运行手册迁出的历史验收

迁移日期：2026-10-16。以下是旧文档原文摘录，来源提交 `5dd8d8691e5cf58420832e32600dda5f6285b879`，不是本次重新执行的验证。记录中的表数、测试数、目录、未发布状态只反映原验收语境，不能作为当前状态或新环境配置。原始私有附件不随仓库交付。

## 固定启动：2026-10-09

来源：`LOCAL_START.md` 的 `## 验证记录`。对应[原功能变更](../archive/2026-10-13-fix-local-startup-configuration/tasks.md)。

> 2026-10-09：启动配置边界与认证设置测试22项通过；Windows真实ACL验证当前用户与SYSTEM两类访问；uv实际加载.env通过；缺少app凭据时固定启动入口安全停止。配置文件及凭据被Git忽略，现有发布包清单不会包含这两个位置。
>
> 用户完成密码配置后，实际`start-local.cmd -CheckOnly`通过：开发库app角色、PG18、业务表及24566端口符合预期。`start-local.cmd`冻结依赖同步、前端构建及真实服务启动成功；首页和/knowledge返回200，/api/health返回ok，/api/auth/config确认注册开启，未登录访问/auth/me和/me/profile返回401。未创建测试账号或写入用户内容。本机应用已运行，网页可访问；本轮仅完成启动验收，真实账号完整业务流程另行验收。

## 备份与恢复：2026-10-09

来源：`DATABASE_BACKUP.md` 的 `## 2026-10-09验收`。对应[原功能变更](../archive/2026-10-13-add-database-backup-rehearsal/tasks.md)。

> - 最终真实开发库备份：`G:\selflore\backups\database\dev-20261009-141055-81db2f66`。
> - 原开发库目前没有用户、卡片或复习记录。真实备份恢复19张表的数据摘要、结构、权限、扩展与迁移历史一致，app角色读权限和限制通过；不能把空表检查宣称为真实用户笔记恢复。
> - 另在新建私有6179实例生成1个合成账号、3张QA/填空/观点卡、分类标签、inline/manual链接、含3成员且重排的混合合集、1次评分和个人资料；完整备份恢复后19张表摘要一致，登录、答案、稳定引用、合集顺序、复习统计和资料读取均通过。未向6171写入合成内容。
> - 24项备份/启动边界测试通过：损坏包、错误路径、占用端口、错误源身份、凭据隔离、失败后停止及密码文件清理。Windows备份ACL核对仅当前用户和SYSTEM，私有实例均已停止，日常24566应用健康检查正常。
> - 成功验收记录：`.cache/restore-rehearsals/restore-20261009-141802-2870b57c/verification.json`；有数据补充记录：`.cache/restore-rehearsals/populated-20261009-141610-3ae6ba79/verification.json`。这些原始记录仅本机保存，通用命令和边界测试随代码交付。
>
> 本次没有生产恢复、操作系统级故障、加密或异地备份验证。OpenSpec变更`add-database-backup-rehearsal`保留未归档。

## 初始工作区迁移：2026-10-08

来源：`apps/api/CARD_MIGRATIONS.md` 的 `## 验收范围`。对应[原功能变更](../archive/2026-10-08-build-card-knowledge-workspace/tasks.md)。

> 在工作区所属的一次性6179 PG18实例中验证了：空库全链、带账号与会话的0001增量升级、最终schema和权限一致、重复执行、并发迁移、篡改 / 缺失历史拒绝、DDL失败、授权失败回滚、13张表外键和 CHECK、资料回填、无演示内容。测试脚本仅允许显式隔离 DSN 和缓存数据目录。
>
> 2026-10-08：用户配置凭据后，对127.0.0.1:6171/selflore_dev完成实际迁移。该库原先只有app.connection_probe，故依次执行0001、0002、0003；原表行数及逐行摘要不变，13张业务表、profile回填条件、应用角色授权和public.pg_trgm已核对，重跑为空操作。未清空数据、未导入示例、未创建账号。
>
> 迁移前完整备份：`G:\selflore\.cache\backups\dev-before-card-migration-20261008-092330\selflore_dev.dump`，pg_restore --list读取成功；同目录verification.json记录目标、版本、备份SHA-256及原表摘要。缓存备份不纳入Git，请保留至验收完成。生产未连接。应用启动没有自动迁移。应用回退保留增量表与原身份表，不提供清空重建脚本或破坏性down迁移。

## 备忘回归：原记录标注2026-10-16

来源：`apps/api/WORKSPACE_TESTING.md` 的 `## 备忘回归（2026-10-16）`。对应[原功能变更](../archive/2026-10-16-add-memos-and-unified-card-navigation/tasks.md)。

> 后端新增tests/test_memos.py、test_memo_schema.py和test_memo_migration.py，覆盖完成幂等、父修订冲突、条目身份、关联及数据库直接写入约束、0005旧数据保留。沿用本文隔离DSN与SELFLORE_TEST_ISOLATED=1要求；pytest会清理测试数据，只能连接一次性库。
>
> 前端在apps/web运行pnpm test、pnpm lint、pnpm build；浏览器沿用24568一次性服务，设置SELFLORE_TEST_ISOLATED=1后运行pnpm test:e2e。新增e2e/memo.spec.ts涵盖创建、排序、关联、完成撤销、冲突、回收站恢复、合集只读及320/390/1280像素检查；旧资料上传、知识复习和观点引用流程一同回归。
>
> 本次联合恢复使用一次性源6179、私有恢复6181，原日常6171未操作；此为受控演练，未修改backup-db.cmd的默认端口或安全限制。23张表结构、权限及数据签名与媒体核验通过，恢复实例在finally停止。发布兼容性模拟可运行apps/api/.venv/Scripts/python.exe -m pytest deploy/tests/test_executor.py，不连接服务器。

## 其他历史状态

原 PROJECT_OVERVIEW 与 MAINTENANCE 中的“未发布／未操作生产”和不同批次测试数量已从当前说明移除，原文仍可由上述来源提交追溯，不转写为当前结论。最新一次工具升级及实际生产发布见[发布验收记录](../approve-memo-release-tools/validation.md)。
