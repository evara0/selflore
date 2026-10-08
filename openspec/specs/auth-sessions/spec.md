# auth-sessions Specification

## Purpose

定义浏览器用户名密码登录后的服务端会话、退出和过期行为，使身份状态可撤销，并避免在前端持久存储认证凭据。

## Requirements

### Requirement: 登录和身份查询

系统 SHALL 在凭据正确且账号可用时建立有明确过期时间的会话。登录失败 SHALL 使用一致的错误反馈，不暴露用户名是否存在；系统 MUST 限制重复失败尝试。浏览器端会话凭据 MUST 通过受保护的 Cookie 传递，不得写入 Web Storage。

#### Scenario: 登录成功

- **WHEN** 可用账号提交正确用户名和密码
- **THEN** 系统 SHALL 建立新会话，返回账号公开资料并设置会话 Cookie

#### Scenario: 登录失败

- **WHEN** 用户名不存在、密码错误或账号已停用
- **THEN** 系统 SHALL 使用相同的对外失败语义，不建立会话

#### Scenario: 重复失败尝试

- **WHEN** 同一来源或用户名在限制窗口内重复提交错误凭据
- **THEN** 系统 SHALL 限制后续尝试，避免无限速猜测

### Requirement: 当前会话与退出

系统 SHALL 提供当前会话查询和退出操作。退出、过期或撤销后，原会话 MUST 无法继续访问受保护 API；登录状态恢复 SHALL 以服务端会话查询结果为准。

#### Scenario: 重新加载页面

- **WHEN** 浏览器保留有效会话 Cookie 并重新加载页面
- **THEN** 前端 SHALL 从服务端恢复当前账号和角色

#### Scenario: 退出

- **WHEN** 已登录用户执行退出
- **THEN** 服务端 SHALL 撤销当前会话并清除浏览器 Cookie

#### Scenario: 已失效会话

- **WHEN** 浏览器携带过期、已撤销或对应账号已停用的会话
- **THEN** 受保护 API SHALL 将其视为未认证

### Requirement: 浏览器请求保护

生产环境默认会话 Cookie MUST 只通过 HTTPS 传输、禁止脚本读取，并明确限制跨站发送。仅显式启用本地部署规格定义的受限临时 HTTP 模式时 SHALL 使用独立的 HTTP 会话 Cookie，MUST NOT 改变默认 HTTPS 安全边界。所有会改变状态的认证请求 MUST 校验同源来源；已登录会话的状态变更 MUST 验证防跨站请求令牌。

#### Scenario: 缺少防跨站请求令牌

- **WHEN** 浏览器以会话 Cookie 请求受保护的状态变更接口，但缺少有效防跨站请求令牌
- **THEN** 系统 SHALL 拒绝请求且不修改数据

#### Scenario: 跨站登录请求

- **WHEN** 登录请求来自未获准的来源
- **THEN** 系统 SHALL 拒绝请求且不设置会话 Cookie
