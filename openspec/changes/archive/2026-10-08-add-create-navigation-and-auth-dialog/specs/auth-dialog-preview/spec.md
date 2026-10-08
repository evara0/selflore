## Purpose

为 SelfLore 提供与现有视觉风格协调的账号入口及登录／注册界面原型，让用户能够预览和操作表单，同时清楚知道真实认证服务尚未接入。

## ADDED Requirements

### Requirement: 打开与关闭账号弹窗

页眉右侧 SHALL 在桌面和移动布局显示登录入口；点击后 SHALL 打开账号弹窗。用户 SHALL 能通过关闭按钮或 Escape 关闭弹窗并返回页面。

#### Scenario: 打开账号界面

- **WHEN** 用户点击页眉登录按钮
- **THEN** 页面 SHALL 显示账号弹窗，包含标题、说明、登录／注册切换和关闭按钮

#### Scenario: 关闭账号界面

- **WHEN** 弹窗打开后用户点击关闭按钮或按 Escape
- **THEN** 弹窗 SHALL 关闭，原页面 SHALL 保持可用

### Requirement: 前端表单原型

弹窗 SHALL 提供用户名和密码输入、登录／注册模式切换；注册模式 SHALL 提供确认密码输入。表单 SHALL 在输入不完整或确认密码不一致时阻止提交。

#### Scenario: 切换至注册

- **WHEN** 用户点击“注册”标签
- **THEN** 弹窗 SHALL 显示注册表单及确认密码字段

#### Scenario: 表单输入不完整

- **WHEN** 必填字段为空，或注册模式下两次密码不一致
- **THEN** 提交操作 SHALL 不可执行

### Requirement: 无认证后端边界

登录与注册提交 MUST 不发送认证请求、不建立登录状态；有效表单提交 SHALL 显示服务尚未接入的明确提示。

#### Scenario: 提交完整登录表单

- **WHEN** 用户填写完整登录表单并点击提交
- **THEN** 页面 SHALL 显示尚未接入认证服务的提示，且 SHALL 不显示登录成功状态

### Requirement: 紧凑的响应式弹窗

账号弹窗 SHALL 在桌面将面板宽度控制在约 520px 以内，在移动端控制在约 340px 以内，并使用相应紧凑的字号、控件尺寸和间距；在移动视口内 SHALL 完整呈现或允许滚动查看内容。

#### Scenario: 窄屏查看账号表单

- **WHEN** 用户在移动宽度打开账号弹窗
- **THEN** 弹窗 SHALL 保持在视口内，字段与提交按钮 SHALL 可访问
