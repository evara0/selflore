# SelfLore

SelfLore 用四个导航页组织个人知识与思考：知识支持问答、填空与 FSRS 复习；观点支持原子笔记和双向链接；合集支持混合卡片编排和独立翻阅；我的展示个人资料、积累和十二周学习足迹。

| 区域 | 当前实现 |
| --- | --- |
| 后端 | Python 3.13、FastAPI、Uvicorn、psycopg、FSRS；uv 锁文件 |
| 前端 | React、TypeScript、Vite、React Router、TanStack Query、安全 Markdown；pnpm 锁文件 |
| 数据库 | PostgreSQL 18，身份基线加13张内容、组织、资料及学习表，SQL增量迁移 |
| 本地端口 | API 24566、Vite 24567、开发数据库6171 |
| 隔离验证 | 一次性数据库6179、浏览器API24568；不得复用业务库 |
| 规格 | 已完成能力见 `openspec/specs/`，历史变更见主项目归档；本机部署OpenSpec独立管理 |

启动、配置、更新与排障见 [MAINTENANCE.md](MAINTENANCE.md)。卡片迁移增加0002与0003，不清空已有数据；现有开发库需要 migrator 凭据才可执行。本次未发布生产。
