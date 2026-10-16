# 卡片工作区 API

所有业务接口以 `/api` 开头，使用既有 HttpOnly 会话 Cookie。写入要求受信任 `Origin` 和当前会话 `X-CSRF-Token`。owner 取自会话，客户端不得提交 owner；管理员不具备读取他人个人内容的权限。

错误：业务错误 `{"detail":{"code":"...","message":"..."}}`；字段错误保留 FastAPI 422 格式，旧认证错误格式兼容。401 未登录、403 Origin / CSRF、404 不存在或非本人、409 修订 / 请求幂等冲突、422 内容非法、503 数据库不可用。

| 接口 | 用途 |
| --- | --- |
| `GET /cards`、`POST /cards` | 本人摘要分页 / 创建卡片 |
| `GET /cards/summary` | 活跃知识、观点、待整理、收藏数 |
| `GET/PATCH /cards/{id}` | 完整详情 / 修订编辑 |
| `POST /cards/{id}/lifecycle` | archive / trash / restore |
| `GET /cards/{id}/links` | outgoing / incoming，按目标去重并返回 origins |
| `POST/DELETE /cards/{id}/links/{target}` | 增删 manual 来源，保留 inline 来源 |
| `GET/POST /topics`、`PATCH/DELETE /topics/{id}` | 分类 / 主题；仍被使用时删除返回 409 |
| `GET/POST /tags`、`PATCH/DELETE /tags/{id}` | 标签管理 |
| `GET/POST /collections`、`GET/PATCH /collections/{id}` | 合集分页、创建、详情、编辑 |
| `POST /collections/{id}/lifecycle` | trash / restore |
| `GET/POST /collections/{id}/items` | 全目录 / 原子批量加入 card_ids |
| `DELETE /collections/{id}/items/{item_id}` | 仅移除引用 |
| `PUT /collections/{id}/order` | 全部 item_ids 恰好一次，事务重排 |
| `GET /reviews/queue`、`GET /reviews/summary` | 到期优先 + 日新额度队列 / 实际学习统计 |
| `GET /reviews/units/{id}/preview` | 四档预计间隔，只读 |
| `POST /reviews/units/{id}/ratings` | FSRS 评分事务，保存响应以便幂等重试 |
| `GET/PATCH /me/profile` | 本人资料及学习设置 |
| `GET /me/summary`、`GET /me/activity` | 卡片积累 / 最近记录分页 |
| `GET /me/heatmap`、`GET /me/pinned-collections` | 本人时区十二周日历 / 最多六个置顶合集 |

`GET /cards` 支持 kind、q、topic_id、tag_id、lifecycle（默认 active）、processing_state、is_bookmarked、sort、limit（1–100）、offset。排序为 updated_desc / created_desc / code_asc / connections_desc；中文 ILIKE 字面匹配，百分号和下划线不会扩展通配范围。摘要不返回答案或完整正文；填空摘要遮蔽答案。分页返回 items / total / limit / offset。

创建卡片示例（UUID 由客户端产生，每次新意图不同，重试同一意图相同）：

```json
{"kind":"knowledge","form":"qa","title":"主动回忆","question_md":"什么是主动回忆？","answer_md":"从记忆中主动提取信息。","topic_ids":[],"tag_ids":[],"client_request_id":"11111111-1111-4111-8111-111111111111"}
```

填空 form=cloze，使用 body_md，其他两面为 null；`{{c1::答案::提示}}` 同编号一单元，c1/c2 两单元。1–99、最多20个独立编号，忽略代码段，拒绝嵌套与空答案。观点 kind=opinion，form=null，只用 body_md。每段 Markdown 最多64 KiB，来源只允许 HTTP(S)。类型和形式创建后不可变，PATCH 不接受它们。

编辑 / 组织 / 生命周期 / manual 链接 / 合集成员写入均带 `expected_revision`。稳定引用格式 `[[UUID|标题]]`，标题仅是提示，展示当前目标标题。纯标题引用保持未解析，代码段不建立关系。正文删除某引用只删除 inline；同一目标的 manual 继续保留。归档 / 回收站目标显示暂不可用。

评分请求带 request_id、rating（1重来 / 2困难 / 3良好 / 4简单）、expected_state_version、expected_content_revision、duration_ms（0–3600000）。服务端取 UTC 时间，状态、学习日志、活动在同事务写入。相同请求键和载荷返回原响应；不同载荷、旧状态或旧内容返回409。FSRS 6.3.2，参数和库版本保存在状态内，关闭 fuzzing，未安装 optimizer。合集阅读和显示答案不会调用评分。

profile 支持 display_name / bio / avatar_color（sage/clay/ink）/ interests / IANA timezone / daily_new_limit（0–100）/ daily_review_goal（1–1000）；修改带 expected_revision。默认旧 username、Asia/Shanghai、20新单元、20复习目标。

今日完成数为本人时区内不同复习单元；积累数为内容卡片。已掌握要求至少一个活跃单元、每个活跃单元均 review 且下次间隔≥21天。学习足迹只计新建、内容更新、复习；收藏、组织、合集操作仅进入最近活动。

完整字段约束可见运行服务的 `/docs` 与 `app/schemas/workspace.py`。表结构和迁移见 [CARD_MIGRATIONS.md](CARD_MIGRATIONS.md)。

## 资料卡与附件
## 备忘与清单

kind=memo、form=null，memo_format为note或checklist，创建后不可变。标题必填，正文body_md可空；note只需标题，checklist需要1–200个memo_items。条目输入为id（客户端生成的稳定UUID）、text（去空白后1–2000字符）、is_completed、target_ids（最多20个本人卡片）。顺序由输入数组决定。备忘不能包含附件、分类或知识问答字段；标签和来源可选。

PATCH /api/cards/{id}带expected_revision；省略memo_items保留原条目，显式数组按稳定ID整体更新，未改完成状态时保留服务器完成时间。创建仍使用client_request_id幂等重试。详情返回memo_items及派生memo_progress。

| 接口 | 行为 |
| --- | --- |
| GET /api/cards?kind=memo&memo_format=checklist | 按形式分页搜索，条目文字参与父卡片搜索 |
| GET /api/memo-items?is_completed=false&q=关键词 | 直接分页事项，返回父卡片ID、标题、修订和目标信息 |
| PATCH /api/cards/{id}/memo-items/{item_id} | expected_revision与is_completed显式目标状态；完成时间由服务器写入，撤销清空 |
| PUT /api/cards/{id}/memo-items/order | expected_revision和包含所有条目恰好一次的item_ids |

父修订冲突返回409；同修订且同完成状态不重复写活动。归档或回收站备忘不能编辑或勾选，恢复保留原条目和时间。链接合并正文、手动及条目来源，按目标去重并保留条目定位。合集中的清单只读；备忘有独立积累与活动，不增加复习单元、掌握数或学习连续天数。

页面规范地址为/cards、/cards/:id、/memos和/memos/:id；原/knowledge、知识及资料详情、/opinions?card=地址保留适配。四主导航为卡片、备忘、合集、我的。

## 资料卡与附件

`kind=reference`，`form=null`，`body_md`为原始摘录，`note_md`为个人说明；原始摘录或至少一个ready附件必需。来源扩展为source_author、source_publisher、source_platform、source_published_on。`attachments`为包含id、caption、alt_text、creator_name的有序数组，每卡最多10图；PATCH用expected_revision整组原子替换。

`GET /api/cards?kinds=knowledge,reference`多类型过滤，与kind互斥。单独kind=knowledge保持旧语义。摘要新增references，合集新增reference_count，活动筛选支持reference。

`GET /api/attachments/config`提供可用状态和实际限制；`POST /api/attachments`使用multipart（file、client_request_id、file_sha256），带现有Cookie／Origin／CSRF。`GET /api/attachments/{id}`及`/content?variant=original|thumbnail`仅本人可读，非本人及未知ID一致404，未登录401。图片private no-store、nosniff，不公开静态媒体目录。图片上传不写学习事件。
