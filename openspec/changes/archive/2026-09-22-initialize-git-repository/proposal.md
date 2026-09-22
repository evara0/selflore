## Why

项目目前没有版本控制基线，无法可靠追溯后续的 OpenSpec 工件和实现变更。应先建立一个范围受控、可安全提交的 Git 仓库基线。

## What Changes

- 在 `G:\selflore` 初始化独立 Git 仓库，不创建远程仓库、不配置远程地址、也不推送。
- 添加简洁的项目介绍 `README.md`，不在其中预先写入后续设计计划。
- 添加根目录 `.gitignore`：忽略本地参考计划目录 `docs/`、本地代理技能目录 `.agents/`，以及常见的密钥、环境文件、缓存、日志和构建输出；保留 `openspec/` 为可跟踪内容。
- 仅暂存和创建安全基线所需的 `README.md`、`.gitignore` 与 `openspec/` 工件；不提交 `docs/` 或 `.agents/`。
- 创建一个清晰标识为初始基线的本地提交。

## Capabilities

### New Capabilities

- `repository-baseline`: 项目 SHALL 具备可追溯的本地 Git 基线，并明确区分应跟踪的 OpenSpec 工件与本地参考材料。

### Modified Capabilities

- 无。

## Impact

受影响的系统为本地工作目录和 Git 元数据。不会增加应用代码、运行时依赖、远程仓库、CI/CD 或部署配置；不会读取或提交任何秘密值。
