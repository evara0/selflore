## Context

源库固定127.0.0.1:6171/selflore_dev。migrator可SET ROLE owner完成全表备份，日常app角色权限不足以读取所有迁移和审计信息。现有pg_dump/pg_restore/initdb/pg_ctl为PG18。

## Goals / Non-Goals

**Goals:** 可重复执行的完整数据库备份和隔离恢复；在线快照一致；凭据不进入日志或Git；保留核验结果。

**Non-Goals:** 不覆盖或恢复源开发库，不实施生产恢复、全局角色备份或操作系统级灾备，不修改既有角色密码。

## Decisions

1. 根目录backup-db.cmd调用PowerShell入口，显式读取用户级迁移凭据，仅传入子进程环境；不加载日常.env。CLI固定源主机、端口、库和角色，检查PG18及工具版本。
2. owner只读REPEATABLE READ事务导出快照；同事务计算全表行数和逐行SHA-256及结构/权限签名，pg_dump使用--snapshot同一快照。成功后生成custom dump、archive.list、文件SHA-256及manifest；失败不得标注完整备份。
3. --rehearse使用新建私有目录initdb，随机临时管理员密码、SCRAM认证、127.0.0.1:6179。端口占用就拒绝，不操作现有测试实例。新建原owner/app/migrator角色和独立恢复库，pg_restore --single-transaction --exit-on-error恢复，完全不使用--clean。演练finally停止所属实例，文件受限权限离线保留。
4. 恢复核验表数据摘要、列、约束、索引、owner、ACL、扩展与迁移历史；以恢复后的app角色测试知识/观点/关联/合集/复习/资料读取。源数据为空时明确记录对应读表已通过但没有真实内容，不创建示例冒充源数据。
5. 备份目录与私有实例目录先限制Windows ACL为当前用户和SYSTEM，密码文件仅存在私有目录且initdb完成后删除；工具日志私有保存、不回显原始错误或数据。固定入口兼容源库迁移凭据已有用户变量。

6. 可保留备份固定在项目backups/database，不归入.cache；私有演练实例保存在.cache/restore-rehearsals。backups整体Git忽略，备份内容不进入现有发布清单。

## Risks / Trade-offs

备份含账号和会话材料 → 私有ACL、Git忽略、发布清单排除；只打印汇总与路径。

一致性事务持续时间 → 仅备份期间保持只读快照；完成及时释放，不停日常应用。

数据库级备份不包含全局角色密码 → 演练重建最小角色，用随机临时密码验证权限；真实恢复说明要求预先准备受控角色。

## Migration Plan

无SQL迁移。backup-db.cmd只备份；-Rehearse备份并演练，或-BackupPath选择已有完整包。只运行本机开发范围，不自动归档。
