# SelfLore

SelfLore 是一个用卡片组织知识与思考的个人空间：事实知识支持问答、填空与间隔复习；原子观点支持稳定引用和双向链接；合集支持混合卡片翻阅；个人主页展示积累与学习足迹。

前端 React / TypeScript / Vite，后端 Python 3.13 / FastAPI / psycopg，数据库 PostgreSQL 18。入口与日常操作见 [项目维护卡](MAINTENANCE.md)，接口见 [工作区 API](apps/api/WORKSPACE_API.md)。

数据库采用 `apps/api/migrations/` 中的不可变 SQL 增量迁移：0001 身份基线、0002 卡片工作区、0003 知识复习。现有数据保留，应用启动不会自动迁移。执行方式见 [卡片迁移说明](apps/api/CARD_MIGRATIONS.md)，测试见 [本地验证](apps/api/WORKSPACE_TESTING.md)。
