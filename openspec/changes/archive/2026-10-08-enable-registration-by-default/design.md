## Context

当前Settings在未配置SELFLORE_ALLOW_REGISTRATION时使用false。前端请求/api/auth/config，仅在registration_enabled为true时显示注册标签。

## Goals / Non-Goals

**Goals:** 正常启动自动开放注册；显式false仍可关闭；前后端策略一致。

**Non-Goals:** 不新增邮箱验证或自动登录，不修改账号权限或数据库，不部署生产。

## Decisions

将后端开关缺省值改为true，保持显式值解析规则和前端配置接口。相较强制前端显示标签，此方式同时开放实际注册接口，避免入口可见但提交被拒绝。更新部署示例为true，防止示例中的显式false覆盖新默认。

## Risks / Trade-offs

公开注册会接受更多账号请求 → 保留现有IP限速、Origin校验、密码哈希和普通用户权限；管理员仍可显式关闭。

## Migration Plan

不需要数据库迁移。重启使用新源码的后端并刷新前端；原有显式false需要移除或改为true。回退源码恢复旧默认。
