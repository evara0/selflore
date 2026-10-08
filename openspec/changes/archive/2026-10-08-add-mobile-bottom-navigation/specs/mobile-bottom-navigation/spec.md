## Purpose

让移动端以底部导航访问页面，同时保留顶部品牌识别。

## ADDED Requirements

### Requirement: 移动端底部导航

窄屏页面 SHALL 显示固定在底部的图标导航，且顶部页面导航 MUST 不显示。

#### Scenario: 窄屏访问
- **WHEN** 视口宽度小于 760px
- **THEN** 用户 SHALL 看见底部导航并能切换页面

### Requirement: 顶部品牌保留

窄屏页面 MUST 保留顶部 LATTICE / SELFLORE 标题。

#### Scenario: 窄屏首页
- **WHEN** 用户打开页面
- **THEN** 顶部 SHALL 显示品牌标题
