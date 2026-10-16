# 开发库备份与隔离恢复

本文统一说明开发库备份、图片联合备份与恢复演练。固定Windows入口在仓库根的PowerShell执行，源目标仅为 `127.0.0.1:6171/selflore_dev`，不能连接生产或替代生产发布备份。

## 准备与命令

需要源库在线、本机PostgreSQL 18工具和迁移角色凭据。脚本优先读取用户级 `SELFLORE_MIGRATOR_PASSWORD`，其次读取当前终端同名变量；不重设角色密码，也不输出凭据。PG工具不在PATH及默认目录时，设置 `SELFLORE_PG_BIN` 为实际bin目录。

日常app连接与迁移凭据独立；备份只从 `apps/api/.env` 补充非秘密的 `SELFLORE_MEDIA_*` 设置，不加载其中的app连接或密码。

```powershell
# 在线开发库完整备份
.\backup-db.cmd

# 新备份并恢复验证到工具自行创建的私有实例
.\backup-db.cmd -Rehearse

# 核验已有备份，不重新备份源库；按提示输入已核对的目录
$backupPath = Read-Host '已有备份目录的完整路径'
.\backup-db.cmd -Rehearse -BackupPath $backupPath
```

登录角色为 `selflore_dev_migrator`，只读事务切换owner。表签名和pg_dump共享同一REPEATABLE READ导出快照，备份期间日常应用可继续运行。

## 格式、文件与保留

备份位于 `backups/database/dev-<时间戳>-<随机标识>/`，包括 `selflore_dev.dump`、`manifest.json`、`archive.list` 和私有工具日志。

| 格式 | 范围与完整性 |
| --- | --- |
| selflore-backup-v2 | 当前含附件结构的数据库及全部ready原图／缩略图；附件清单与dump来自同一快照，核对字节数与SHA-256 |
| selflore-backup-v1 | 兼容无附件表的旧备份；含附件结构的数据库不能伪装成数据库-only v1包 |

ready清单包含回收站、归档及尚未被卡片引用的ready附件；不包含上传中或未知孤立文件。缺文件、大小或hash不符时不会写入完整成功清单。图片启用前的目录准备见[媒体配置](MEDIA_STORAGE.md#本机启用)。

备份及文件仅允许当前Windows用户和SYSTEM读取，整体被Git忽略，不随应用发布。备份不会自动删除；受限文件权限不等于静态加密或异地容灾，需要时另存受控介质或异地存储。

## 恢复演练边界

- 只在工具自行创建、随机密码SCRAM认证的私有6179实例恢复；端口被占用即拒绝，不会停止别人的实例、覆盖开发库或生产库。
- 目标是随机生成的新数据库，PG恢复使用单事务并遇错停止，不使用 `--clean`。
- 恢复前核对manifest和文件摘要，恢复后比较源清单中全部表的数据签名、结构、权限、扩展和迁移历史，并核验app角色权限。表数取自实际清单，不写死历史数量。
- v2还会恢复到独立媒体目录，核验原图／缩略图hash，并用临时本人会话探测图片权限；探测会话随后清除。开始、结束和耗时供诊断读取。
- 演练资料保存在 `.cache/restore-rehearsals/`，成功记录为 `verification.json`。完成或失败后工具停止所属实例并清理临时密码文件；离线数据目录仍按敏感资料保留。

数据库备份不包含全局角色定义及原角色密码，演练会以随机密码重建所需角色。真正恢复到日常或生产环境需要另行核对目标、保留当前数据、准备角色和连接配置；本文入口不执行该操作。

## 生产与历史记录

生产由维护者本机发布流程执行数据库与媒体一致备份、生成受保护收据并下载核验副本，不能把本机固定开发库命令改成生产连接。程序升级入口见[维护卡](MAINTENANCE.md#程序更新到目标环境)。

旧批次的实际目录、表数和测试结果已迁至[历史验收记录](openspec/changes/consolidate-public-operations-docs/historical-validation.md)，不作为新环境前提。后续每次演练应记录自己的目标、摘要、时间和结果。
