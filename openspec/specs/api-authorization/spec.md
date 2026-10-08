# api-authorization Specification

## Purpose

定义 SelfLore API 对访客、普通用户和管理员的授权边界，保证权限由服务端决定，并为后续个人内容的隔离提供一致的判定规则。

## Requirements

### Requirement: 默认拒绝受保护操作

受保护 API SHALL 在服务端验证当前有效会话及所需权限。未认证请求 SHALL 返回未认证结果；已认证但权限不足的请求 SHALL 返回禁止访问结果。客户端提交的角色或账号 ID MUST 不能替代服务端身份判断。

#### Scenario: 未登录访问管理接口

- **WHEN** 访客请求管理员接口
- **THEN** 系统 SHALL 拒绝访问并返回未认证结果

#### Scenario: 普通用户访问管理接口

- **WHEN** 普通用户携带有效会话请求管理员接口
- **THEN** 系统 SHALL 拒绝访问并返回禁止访问结果

### Requirement: 账号范围与角色变更

用户本人操作 SHALL 仅作用于当前会话所属账号；管理员操作 SHALL 以数据库中的当前角色与可用状态为准。角色变更或账号停用后，旧会话 MUST 不再保有旧权限。

#### Scenario: 伪造目标账号

- **WHEN** 普通用户在本人资料或密码请求中提交其他账号 ID
- **THEN** 系统 SHALL 仍只处理当前会话对应账号，或拒绝该请求

#### Scenario: 管理员被降级

- **WHEN** 管理员角色被改为普通用户
- **THEN** 其既有会话 SHALL 失效，之后不得继续调用管理接口
