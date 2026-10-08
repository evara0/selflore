# database-migrations Specification

## Purpose

定义 SelfLore 账号相关数据库结构的版本管理和执行约束，使开发与生产环境能够按相同顺序升级，并保持运行账号与结构变更权限分离。

## Requirements

### Requirement: 可追踪的版本迁移

系统 SHALL 以有序、可校验的迁移记录创建账号、会话和账号管理审计结构。迁移 MUST 在指定环境执行，重复执行已完成版本 SHALL 不重建表或覆盖现有账号；已执行文件发生变化 SHALL 报错。

#### Scenario: 首次升级

- **WHEN** 授权迁移账号对已初始化的开发库执行迁移
- **THEN** 系统 SHALL 创建所需结构并记录已执行版本，不修改生产库

#### Scenario: 重复升级

- **WHEN** 相同版本迁移再次针对同一库执行
- **THEN** 系统 SHALL 验证记录后跳过，不清空或重建现有数据

#### Scenario: 历史迁移被修改

- **WHEN** 已执行的迁移文件内容与记录的校验值不一致
- **THEN** 系统 SHALL 停止，不继续应用后续版本

### Requirement: 最小数据库权限

结构变更 MUST 由 migrator 显式切换 owner 身份执行。应用数据库角色 SHALL 仅获得账号功能所需的数据访问权限，MUST 不能创建或修改数据库结构，也不能读取迁移管理表。

#### Scenario: 应用账号尝试迁移

- **WHEN** 使用应用数据库角色运行迁移命令
- **THEN** 命令 SHALL 拒绝执行，不得建立或修改表

### Requirement: 失败后可恢复

单个迁移及其版本记录 SHALL 在同一事务中提交；失败 SHALL 回滚该版本的全部变更。迁移执行 SHALL 防止两个进程同时应用同一版本。

#### Scenario: 迁移中途失败

- **WHEN** 某版本在建表或授权过程中失败
- **THEN** 该版本 SHALL 保持未应用状态，已有账号数据不受影响
