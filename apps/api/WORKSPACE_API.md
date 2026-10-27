# 卡片工作区 API

所有业务接口以 `/api` 开头，使用既有 HttpOnly 会话 Cookie。写入要求受信任 `Origin` 和当前会话 `X-CSRF-Token`。owner 取自会话，客户端不得提交 owner；管理员不具备读取他人个人内容的权限。

错误：业务错误 `{"detail":{"code":"...","message":"..."}}`；字段错误保留 FastAPI 422 格式，旧认证错误格式兼容。401 未登录、403 Origin / CSRF、404 不存在或非本人、409 修订 / 请求幂等冲突、422 内容非法、503 数据库不可用。

| 接口 | 用途 |
| --- | --- |
| `GET /cards`、`POST /cards` | 本人摘要分页 / 创建卡片 |
| `GET /cards/summary` | 活跃知识、观点、资料及备忘数量；待整理与收藏不计备忘 |
| `POST /sources/resolve` | 公开来源建议，不创建或修改卡片 |
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

`GET /cards` 支持 kind（knowledge／opinion／reference／memo）、kinds（与kind互斥的逗号分隔类型集合）、memo_format（须配合kind=memo）、q、topic_id、tag_id、lifecycle（默认 active）、processing_state、is_bookmarked、sort、limit（1–100）、offset。排序为 updated_desc / created_desc / code_asc / connections_desc；中文 ILIKE 字面匹配，百分号和下划线不会扩展通配范围。摘要不返回答案或完整正文；填空摘要遮蔽答案。分页返回 items / total / limit / offset。

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

## 备忘与清单

kind=memo、form=null，memo_format为note或checklist，创建后不可变。标题必填，正文body_md可空；note只需标题，checklist需要1–200个memo_items。条目输入为id（客户端生成的稳定UUID）、text（去空白后1–2000字符）、extra_values（固定两个可空文本，各最多2000字符）、is_completed、target_ids（最多20个本人卡片；新增仅限事实知识，同一行已有其他类型关系可保留）。顺序由输入数组决定。备忘不能包含附件、分类或知识问答字段；标签和来源可选。

PATCH /api/cards/{id}带expected_revision；省略memo_items保留原条目，显式数组按稳定ID整体更新，未改完成状态时保留服务器完成时间。创建仍使用client_request_id幂等重试。详情返回memo_items及派生memo_progress。

| 接口 | 行为 |
| --- | --- |
| GET /api/cards?kind=memo&memo_format=checklist | 按形式分页搜索，条目文字参与父卡片搜索 |
| GET /api/memo-items?is_completed=false&q=关键词 | 直接分页事项，返回父卡片ID、标题、修订和目标信息 |
| PATCH /api/cards/{id}/memo-items/{item_id} | expected_revision与is_completed显式目标状态；完成时间由服务器写入，撤销清空 |
| PUT /api/cards/{id}/memo-items/order | expected_revision和包含所有条目恰好一次的item_ids |

父修订冲突返回409；同修订且同完成状态不重复写活动。归档或回收站备忘不能编辑或勾选，恢复保留原条目和时间。链接合并正文、手动及条目来源，按目标去重并保留条目定位。合集中的清单只读；备忘有独立积累与活动，不增加复习单元、掌握数或学习连续天数。

页面规范地址为/cards、/cards/:id、/memos和/memos/:id；原/knowledge、知识及资料详情、/opinions?card=地址保留适配。四主导航为卡片、备忘、合集、我的。

### 多字段清单兼容约定

清单的memo_columns始终保存三个1–40字符列名，默认`["条目","字段 2","字段 3"]`；memo_column_count为1–3，默认1。text是首列主要文字，extra_values依次对应第二／第三列，勾选不计入内容字段。减少count仅隐藏，不删除名称和值；界面增加count后恢复。详情、合集阅读及未完成事项返回全部槽位数据（展示按count），搜索覆盖全部槽位，包括隐藏值。旧单文本请求仍有效；旧PATCH按稳定行ID保留省略的extra_values，显式`["",""]`用于清空，删除行仍删除其字段和关系。

行内知识复用`POST /cards`，kind固定knowledge，沿用qa／cloze规则和client_request_id幂等重试。知识创建和父清单保存是独立事务：创建成功后仍须保存清单；取消或父保存失败不删除已建知识。界面保留父草稿和当前行，但关闭／刷新未保存页面仍会丢失草稿，应先保存。勾选不改变知识调度或掌握状态。

## 资料卡与附件

获取来源建议见[来源链接解析](#来源链接解析)，图片仍由用户上传。

`kind=reference`，`form=null`，`body_md`为原始摘录，`note_md`为个人说明；原始摘录或至少一个ready附件必需。来源扩展为source_author、source_publisher、source_platform、source_published_on。`attachments`为包含id、caption、alt_text、creator_name的有序数组，每卡最多10图；PATCH用expected_revision整组原子替换。

`GET /api/cards?kinds=knowledge,reference`多类型过滤，与kind互斥。单独kind=knowledge保持旧语义。摘要新增references，合集新增reference_count，活动筛选支持reference。

`GET /api/attachments/config`提供可用状态和实际限制；`POST /api/attachments`使用multipart（file、client_request_id、file_sha256），带现有Cookie／Origin／CSRF。`GET /api/attachments/{id}`及`/content?variant=original|thumbnail`仅本人可读，非本人及未知ID一致404，未登录401。图片private no-store、nosniff，不公开静态媒体目录。图片上传不写学习事件。

## 来源链接解析

`POST /api/sources/resolve`，请求`{"url":"https://example.com/article","mode":"auto"}`；mode为auto（默认）或webpage（强制普通网页）。要求会话、受信任Origin及CSRF，单账号进程内10次/分钟，并发受限返回429；非法／不安全输入422。

响应包含category(webpage/x)、method(webpage/x_oembed)、status(success/partial/unavailable)、fallback_reason（无回退为null）、fields。fields只含提取到的source_title、source_author、source_publisher、source_platform、source_published_on。success表示有标题和作者，不表示所有来源字段齐全。外站失败以200和unavailable及安全error代码返回，不泄露响应或内部地址；X专用失败会先回退普通网页。该操作不写卡片、不下载图片；边界与限制见[快速收录说明](../../handbook/SOURCE_CAPTURE.md)。


## 统一标签与兼容协议（0007）

四类内容共用同账号标签，每卡0至30个不同ID；1至80字符名称按NFKC和Unicode首尾空白规范化，同账号规范名唯一，大小写及内部空白不折叠。`POST /tags` 重名返回409，`detail.existing_tag={id,name}` 仅包含本人已有项，可直接选用。重命名碰撞返回409；被正常、归档或回收站卡片引用时删除返回409，不隐式合并或删除内容。

新创建／编辑提交 `taxonomy_mode: "unified"` 与 `tag_ids`；统一模式不提交 `topic_ids`（即使空数组也不提交）。新PATCH仅在tag_ids出现时替换完整集合；缺省标签字段保留。返回 `tags/tag_ids` 是完整规范集合，`taxonomy_mode` 为unified；`topics/topic_ids` 仅为旧主题来源投影。卡片写入继续使用修订、事务及请求幂等规则，升级前已成功创建请求的原载荷重试返回原卡片。

| 查询 | 标签参数及统计 |
| --- | --- |
| `/cards` | 重复 `tag_ids=UUID&tag_ids=UUID`，`tag_match=all`（默认）或any；total为卡片数 |
| `/reviews/queue` | 同上；仅有效知识单元，不改变额度、顺序或评分；items计单元 |
| `/memo-items` | 同上；按所属清单筛选后分页，total为事项数 |
| `/tags` | card_count为本人active卡片去重数，跨四类含备忘 |

筛选ID去重后至多30个，空集合不限制标签，未知模式／超限422，不存在与他人ID统一404。all要求全部，any要求至少一个；与关键词、类型、生命周期等取AND。不以JOIN重复计算卡片或单元。

过渡期保留单值topic_id/tag_id及 `/topics` CRUD。旧topic筛选映射规范ID并保留原kind范围，旧tag跨类型；两者同时取AND。旧参数与新tag_ids混用422。topics响应带Deprecation与successor-version Link；本次不删除旧API。

旧卡片请求缺少taxonomy_mode：创建合并topic/tag来源；PATCH只替换显式出现的legacy_topic／legacy_tag分区，保留其他来源及统一写入来源。旧主题仍校验原kind、知识／资料最多一个、备忘不接收主题。旧接口重命名作用于规范标签，所有别名显示同步；删除会使该规范标签全部别名不可用。旧别名ID不复用，不存在与他人对象均404。

页面URL使用重复tag_ids与tag_match并保留q、type、state、bookmarked、card、sort、lifecycle；改变标签清除offset。旧 `/knowledge`、`/opinions` 与Cards的topic/tag、Review的topic仍解析，保留原筛选类型范围；无效旧链接提示不可用，用户可清除筛选，不静默放宽。
