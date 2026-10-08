## Purpose

确保布局框架的标题、说明和半透明内容面板在不同视口中保持可读且互不遮挡。

## ADDED Requirements

### Requirement: 清晰标题区

首页标题、说明文字和标签 SHALL 保持独立的垂直空间，MUST NOT 相互重叠。

#### Scenario: 桌面视口

- **WHEN** 用户在常见桌面宽度查看首页
- **THEN** 标题、说明与标签 SHALL 全部可读且不重叠

### Requirement: 受控面板排版

半透明内容面板中的占位文字 MUST 保持在面板边界内，并保留可见留白。

#### Scenario: 窄屏视口

- **WHEN** 用户在窄屏查看页面
- **THEN** 面板文字 SHALL 换行或缩放而不溢出
