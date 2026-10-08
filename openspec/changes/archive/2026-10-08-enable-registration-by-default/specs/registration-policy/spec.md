## Purpose

规定SelfLore公开注册的缺省策略及前端入口展示，使用户在正常启动应用时无需手动开启注册，同时使部署者仍能通过显式配置关闭注册，并保持现有账号安全校验。

## ADDED Requirements

### Requirement: 默认开放公开注册
系统 SHALL 在开发和生产环境未设置公开注册开关时启用公开注册，并通过配置接口报告启用；前端 SHALL 在配置报告启用时展示可使用的注册标签。

#### Scenario: 无手动开关启动
- **WHEN** 应用启动时未设置SELFLORE_ALLOW_REGISTRATION
- **THEN** GET /api/auth/config返回registration_enabled为true，登录弹窗显示注册标签

### Requirement: 支持显式关闭
系统 SHALL 保留显式false关闭公开注册的行为：配置报告关闭，前端隐藏注册标签，注册接口拒绝请求。

#### Scenario: 显式关闭注册
- **WHEN** 应用配置SELFLORE_ALLOW_REGISTRATION=false
- **THEN** 配置接口报告false且公开注册接口返回403

### Requirement: 保留注册安全规则
系统 SHALL 继续校验用户名唯一性、密码长度及请求频率，仅创建普通用户及默认资料，并在注册成功后要求登录。

#### Scenario: 创建普通账号
- **WHEN** 用户在默认开启状态提交符合校验的注册信息
- **THEN** 注册接口创建普通账号和默认资料，前端提示注册成功并切换到登录
