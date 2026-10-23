## Why

备忘发布包已通过全部门禁，但服务器批准的工具摘要与本地三个文件不一致，阻止既有受限管理员代理继续发布。用户授权更新一次批准版本。

## What Changes

- 为已核验候选 `20261016024908-0e6e771f` 准备固定摘要的一次性管理员升级资料。
- 仅更新批准快照中的 `client.py`、`protocol.py`、`tests/test_executor.py` 及配置中的对应摘要，保存旧版本以便回退。
- 具备管理员入口时执行升级、重新预检并继续同包发布；入口不可用时交付已核验命令并记录阻塞。

## Capabilities

### New Capabilities

无。一次性批准配置更新，设置 `skip_specs: true`。

### Modified Capabilities

无。不扩大既有管理员代理动作或 sudo 授权，不改变产品要求。

## Impact

服务器 `/usr/local/lib/selflore-admin/v1` 的批准快照和配置；项目私有 `local-deployment/admin-upgrades` 中的升级资料；本变更实施记录。保持应用候选、入口脚本、sudo 规则和未提交前端修改不变。
