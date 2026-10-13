## Why

开发库与端口已确定，但日常启动仍需手动注入连接参数。用户要求固定本地配置，能够一次配置密码后使用同一入口启动应用。

## What Changes

- 提供本地.env及无秘密模板，通过uv明确加载配置。
- 提供交互式密码配置，将app角色密码写入本机忽略目录中的libpq凭据文件；迁移凭据独立管理。
- 提供固定启动命令，先只读检查开发库和应用权限，再构建前端并启动24566的统一Web/API入口。
- 配置缺失、错误角色、目标、数据库不可用和端口占用时给出不含秘密的诊断；不自动初始化或迁移数据库。

## Capabilities

### New Capabilities
- `local-startup-configuration`: 项目内固定配置、凭据及统一应用启动检查。

### Modified Capabilities
无。现有local-start-tab-launch独立启动API/Web的契约保持有效；本次不修改外部Start Tab配置。

## Impact

项目启动脚本、后端本地CLI、配置模板、测试与维护说明。复用uv及现有Python环境，无新增依赖、数据库结构或生产操作。
