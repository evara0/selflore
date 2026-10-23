## Why

用户要求实施公开文档审查后的第1、2步：修正模板与过期内容，收敛重复产品概览和运行说明。当前维护文档把历史验收叙述混为当前状态，且迁移、启动和图片说明分散重复，影响新克隆读者理解。

## What Changes

- 替换前端模板 README，精简 API README，仅列各自专用命令、目录及说明入口。
- 将产品概览统一到根 README，移除无当前入链的重复 PROJECT_OVERVIEW；维护卡保留必要环境、更新、日志及恢复入口。
- LOCAL_START 负责固定 Windows 启动，AUTH_CONFIGURATION 负责通用 API 配置；数据库初始化与增量迁移分工，迁移清单按源码顺序呈现。
- 删除 API 空重复标题，修正摘要字段等与当前实现不符的描述；合并备份／媒体操作的重复正文，保留安全边界和监控指标。
- 将历史验收节移入本变更记录并链接原对应功能变更，区分历史叙述、当前操作和仅本机发布材料。
- 校验所有当前公开说明中的链接、锚点、命令入口及迁移版本。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。遵守现有 project-overview 要求，本次只修正文档实现与组织方式，设置 skip_specs。

## Impact

根 README、维护／启动／备份／媒体文档，两个应用 README，以及 API 的数据库、迁移、认证、接口和测试说明；删除 PROJECT_OVERVIEW.md。不改源代码、SQL、目录布局、忽略规则、CI、权限或许可证；不自动提交、推送或归档。
