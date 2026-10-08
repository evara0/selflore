## Purpose

为 SelfLore 的开发和生产环境提供一致的 PostgreSQL 首次初始化入口，使独立实例能得到相同的角色隔离、对象所有权和最小测试结构，同时避免泄露凭据或覆盖现有数据。

## ADDED Requirements

### Requirement: 显式目标选择

初始化命令 SHALL 要求调用者选择 `dev` 或 `prod`，显式指定连接主机、端口与管理员角色；它 MUST 仅在指定实例中创建与环境对应的数据库和角色。

#### Scenario: 初始化开发环境

- **WHEN** 调用者选择 `dev` 并提供可用的管理员连接信息
- **THEN** 命令 SHALL 以 `selflore_dev` 为目标数据库，且不得修改 `selflore_prod`

#### Scenario: 参数或连接无效

- **WHEN** 环境值无效、端口缺失或管理员连接失败
- **THEN** 命令 SHALL 失败并给出可操作的错误，不创建任何数据库对象

### Requirement: 独立角色与所有权

每个环境 SHALL 拥有不可登录的 owner、可登录的 migrator 与可登录的 app 角色。migrator MUST 能显式切换到 owner 来创建对象；app MUST 不能切换到 owner，也不能创建或更改结构。

#### Scenario: 新环境初始化

- **WHEN** 目标环境尚无对应角色和数据库
- **THEN** 命令 SHALL 创建环境专属角色与数据库，建立所需成员关系及最小连接权限

#### Scenario: 应用权限

- **WHEN** 以 app 角色访问初始化完成的数据库
- **THEN** 该角色 SHALL 能读取测试表，且不得写入测试表、建表或获得对象所有权

### Requirement: 最小测试结构

初始化命令 SHALL 在专用 `app` schema 中创建一张无业务数据的测试表，表和 schema MUST 由 owner 持有。

#### Scenario: 空数据库初始化

- **WHEN** 数据库首次初始化
- **THEN** 命令 SHALL 创建 `app.connection_probe`，且不插入任何业务记录

### Requirement: 重复执行与凭据处理

命令 MUST 可以对已正确初始化的环境重复执行；重复执行 SHALL 保留现有数据和登录密码。若同名对象与预期所有权、结构或角色权限冲突，命令 MUST 失败，不自动删除或接管对象。密码 MUST 从安全输入获取，不写入仓库或普通命令行参数。

#### Scenario: 重复执行

- **WHEN** 对已正确初始化的环境再次执行命令
- **THEN** 命令 SHALL 成功且不重置密码、不清空或重建测试表

#### Scenario: 同名对象冲突

- **WHEN** 目标数据库、schema、表或角色已存在但配置与预期不符
- **THEN** 命令 SHALL 报错停止，不执行破坏性修复
