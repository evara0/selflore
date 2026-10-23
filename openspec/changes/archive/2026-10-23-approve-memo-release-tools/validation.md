## 已完成

- 候选 `20261016024908-0e6e771f`，提交 `b520cacc85e79321ff7b1d6ae19318852b0e2398`：所有发布门禁通过且 `promotable: true`；VerifyReleaseId 返回 Artifact and build evidence verified。
- 与服务器批准快照只存在 `client.py`、`protocol.py`、`tests/test_executor.py` 三个差异。
- 使用相同部署密钥只读尝试 root 身份，返回 Permission denied；未执行 root 命令。既有代理只有 backup、restart、status，没有升级动作。
- 升级资料来自候选冻结 tools；固定旧配置，新配置仅更新三个工具摘要，管理员入口及 broker 摘要保持一致。
- 离线 6 项检查通过：正确资料、篡改拒绝、多余工具拒绝、目标变更拒绝、工具摘要不一致拒绝、所有替换文件摘要及语法。
- 已上传部署账号私有目录并由服务器重新计算 SHA-256 核验；服务器 Python 语法检查通过。没有修改正式批准快照。

## 资料与交接

- 本地私有目录：`G:/selflore/local-deployment/admin-upgrades/20261016024908-0e6e771f`。
- 远端私有待办：`/home/selflore-deploy/admin-upgrades/20261016024908-0e6e771f`。
- `root-commands.sh` 为管理员复制到 root 私有目录后核验、执行的具体命令；`rollback-command.txt` 为回退命令；`validation.json`、`upload.json` 为准备证据。
- upgrade.py SHA-256：`1e468d31c5a22c8990a42a5918f89bcdb799e85aa3f12bae67ecdfe9041c301d`。
- bundle.json SHA-256：`cb621d89f017b0c262cfdc149b446ac01acd4a64251115114fc6aa9fade4ef97`。
- 执行后旧副本保留在 root 私有资料目录的 `previous.json`；常规异常自动恢复，进程强杀中断可执行 `upgrade.py --rollback`，随后重新 Doctor。

## 实际升级与发布

用户已在管理员终端执行升级，返回固定摘要、前置状态和升级后验证全部成功。随后只读复核新版 root 受保护快照与本地批准工具完全一致。

标准 Doctor 暴露工具升级兼容问题：对仍运行旧包的管理员 status 使用新版工具目录，Engine.manifest 拒绝旧工具摘要。没有将这一失败标为通过。

已完成一次性只读过渡预检（私有 `transition-preflight.py`、`transition-preflight.json`）：保留 Doctor 的 SSH、主机、配置保护、sudo 精确权限、PG18 migrator 身份、服务入口、版本、readiness 与健康检查；调用受保护管理员模块的只读 load_configuration 验证新版工具。旧包用本机已固定的旧配置摘要及逐项验证的旧 executor 核验归档、解包内容、stage 和 current。结果 approved、immutable_verified、database_identity、ready 均为 true，当前旧包为 `20261014081003-d33c8667`，提交 `94dee58fcf44b80f2263e6469bde62993a6aaf70`。

按已有分阶段入口完成同包发布；未改动控制器、管理员代理或其授权动作。

- Stage 成功；受限代理 AdminBackup 返回 verified、snapshot_consistent 均为 true。
- 生产备份时间为北京时间 2026-10-16 11:19:53，包含数据库与两张图片；本机 `backups/production/20261016024908-0e6e771f/verified.json` 验证成功。
- 本机备份整体 SHA-256：`65fa8f2f02df105bf640cb237afad08b881bbb93b100ecb223aff263d0e4e3f4`。
- Migrate 成功，实际新增 `0006_memo_cards`；历史 0001–0006 完整，迁移记录 ok 为 true。
- Activate、Status、AdminStatus 均成功；实际 current 和 phase 分别为 `20261016024908-0e6e771f`、activated，rollback 为 null，前一版本为 `20261014081003-d33c8667`。
- 激活后完整标准 Doctor 通过：ok、approved、immutable_verified、database_identity、ready 全为 true；实际提交 `b520cacc85e79321ff7b1d6ae19318852b0e2398`。其检查包含回环和公网 API 版本、前端版本、健康及 release-ready。
- 证据：私有发布目录的 `target-attempts.json`、`target-state.json`，私有备份目录的 `receipt.json`、`verified.json` 及过渡预检结果。

## Remaining limitations

跨工具版本的原始 Doctor 兼容问题尚未修正为通用能力，记录于本设计；本次采用显式记录的只读过渡核验和已有分阶段入口完成，激活后标准 Doctor 已完整通过。相同批准工具的普通发布不需要本次过渡步骤。本次没有扩大管理员权限。

本次没有前端展示代码变化，视觉审查不适用。未改动独立的 mobile builder credit 工作区内容；本运维变更保留为已完成、未归档的记录。
