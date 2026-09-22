## Purpose

提供与参考图相同的结构气质、但不复制其内容的 SelfLore 前端布局框架。

## ADDED Requirements

### Requirement: 布局外壳

前端 SHALL 显示线条网格背景、顶端标题导航栏和不会完全遮挡背景的半透明主内容面板。

#### Scenario: 访问首页

- **WHEN** 用户打开前端首页
- **THEN** 用户 SHALL 同时看见网格背景、导航栏和半透明内容区域

### Requirement: 导航占位页

导航栏 SHALL 提供多个可选页面，选择页面 MUST 切换对应的空白或模拟内容区域。

#### Scenario: 切换导航

- **WHEN** 用户选择另一导航项
- **THEN** 主内容区域 SHALL 显示该导航项的占位内容

### Requirement: 本地运行

项目 MUST 通过 pnpm 在端口 `24567` 启动。

#### Scenario: 启动开发服务器

- **WHEN** 开发者运行项目启动命令
- **THEN** 前端 SHALL 在 `http://localhost:24567` 可访问
