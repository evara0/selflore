## Purpose

为 SelfLore 项目建立可审查、可追溯的版本控制起点，并清楚隔离需要共享的工程工件与仅供本地参考或代理运行的内容。

## ADDED Requirements

### Requirement: 本地仓库基线

项目根目录 SHALL 是一个独立的有效 Git 工作树，并包含一份简洁的项目介绍。该介绍 MUST 仅说明项目的当前基本信息，不得把尚未确认的产品或技术设计作为既定范围。

#### Scenario: 验证初始化结果

- **WHEN** 在项目根目录执行 Git 状态查询
- **THEN** Git SHALL 识别该目录为工作树，且基线提交中包含项目介绍文件

### Requirement: 可跟踪工件与本地材料隔离

版本控制 SHALL 跟踪 `openspec/` 下的配置、进行中的变更及归档占位工件。版本控制 MUST 忽略 `docs/` 和 `.agents/`，并且 MUST 忽略常见的环境文件、凭据、日志、缓存与构建输出。

#### Scenario: 验证初始提交范围

- **WHEN** 审查初始基线提交的文件列表
- **THEN** 其中 SHALL 包含 `.gitignore`、`README.md` 与 `openspec/` 的安全工件，且 MUST 不包含 `docs/`、`.agents/`、凭据或环境文件

### Requirement: 本地优先的初始化

本变更 MUST 仅建立本地 Git 基线。它 MUST NOT 创建或配置远程仓库、修改 Git 身份、推送提交，或引入应用代码、依赖、CI/CD 与部署配置。

#### Scenario: 验证外部系统未被改动

- **WHEN** 初始化完成
- **THEN** 项目 SHALL 具有本地提交，且不存在由本变更创建的远程地址或远程推送记录
