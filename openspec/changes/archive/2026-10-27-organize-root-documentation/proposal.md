## Why

项目根目录有八份 Markdown，项目入口与专项操作说明混排；快速收录说明还有一整节重复内容。需要让根目录保持简洁，同时保留现有操作步骤和可访问的公开文档导航。

## What Changes

- 根目录保留 README、CONTRIBUTING 和 AGENTS 三份入口／约定文档。
- 将本地启动、日常维护、数据库备份、图片存储和资料快速收录五份专项说明移入受版本控制的 handbook 目录。
- 更新 README 目录树、文档导航，以及应用说明和手册之间的相对链接。
- 合并快速收录中重复的网络限制与代理计划章节。
- 保持被忽略的 docs 本机资料、历史 OpenSpec 和独立修复 worktree 原状。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-overview`：明确专项公开手册的归属、根入口导航和迁移后的链接维护要求。

## Impact

仅调整公开 Markdown 的位置、重复正文和链接；不改变代码、命令的执行目录、数据库、忽略规则或部署流程。不自动提交、推送或归档。
