## ADDED Requirements

### Requirement: 专项公开手册集中管理

项目 SHALL 在根目录保留项目概览、贡献指南和代理工作约定，将启动、维护、备份、媒体和资料收录的专项公开手册集中到受版本控制的 handbook 目录。根 README SHALL 提供目录说明和直接文档导航。迁移后当前公开文档的相对链接及锚点 MUST 保持有效，MUST NOT 依赖被忽略的本机 docs 目录。完全重复的说明 SHALL 合并为单一正文，保留原有操作边界。

#### Scenario: 从项目首页查找启动手册
- **WHEN** 协作者从根 README 查找本地启动、备份或维护说明
- **THEN** 导航 SHALL 直接打开随仓库交付的 handbook 手册，手册中的应用及历史记录链接保持有效

#### Scenario: 阅读资料收录的网络限制
- **WHEN** 协作者阅读资料收录手册
- **THEN** 网络限制与代理计划 SHALL 只有一份正文，保留现有能力限制和后续计划
