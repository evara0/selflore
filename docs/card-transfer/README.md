# 卡片 JSON / ZIP 交换 v1

这是卡片内容备份和迁移格式，不是全站灾备。包括全部类型、全部生命周期、正文、来源、标签、收藏、整理状态、清单隐藏列及完成时间、卡片关系和关联原图。不包括合集编排、账号资料、活动日志、复习历史／调度或未关联图片。导入只创建新卡，知识卡从新状态复习，原卡不会被覆盖。新 ID、编号、修订号与创建时间由目标系统分配。

## 用 AI 生成

将 `v1.schema.json` 和 `example.json` 连同以下提示词交给 AI：

> 请把我提供的材料整理成 SelfLore cards v1 JSON，只输出一个合法 JSON 对象，不加代码围栏或说明。顶层 format 为 selflore.cards，version 为1，cards 是数组。每张卡片填写文件内唯一 key（1–80个 ASCII 字母数字、短横线或下划线）、kind、title 和对应内容。knowledge 的 qa 形式填写 question_md 和 answer_md；cloze 形式填写 body_md，填空格式如 {{c1::答案::提示}}。opinion 填写 body_md；reference 填写原始摘录 body_md 和可选 note_md；memo 的 note 形式可只有标题，checklist 形式需至少一个 memo_items 条目。条目使用局部 key、text、extra_values 两个附加字符串、is_completed 和 target_keys。tags 使用名称，不编造数据库 UUID。文件内引用写成 [[card:目标key|标题]]，link_keys 表示手工关系，target_keys 表示条目关系；目标必须在同一文件中，不能指向自身。未知来源不编造，不输出 owner_id、id、revision 或 client_request_id。不要生成图片资产；需要原图时由用户使用实际 ZIP 包。遵守 Schema 和下列语义规则。

AI 生成内容仍需人工检查；来源收录不代表事实核验。

## 结构和语义

- 顶层必填 `format`、`version`、`cards`；可选 `assets` 和只读 `export_info`。未知字段和未知版本拒绝，禁止重复 JSON 对象键和非有限数值。UTF-8，可带 BOM。
- 卡片 kind 为 knowledge/opinion/reference/memo。form 为 qa/cloze（仅知识）；memo_format 为 note/checklist（仅备忘）。完整字段类型与长度见 Schema；类型间互斥、填空和引用是额外的服务端语义校验。
- 标签按 NFKC 和去首尾空白规范化，复用本人同名标签，最多30个；大小写和内部空白有区别。
- `processing_state` 默认 inbox，可选 organized；`is_bookmarked` 默认 false；`lifecycle` 默认 active，可选 archived/trashed。归档和回收站卡也会被完整导出。
- `memo_columns` 始终保留三个列名，`memo_column_count` 为1–3，仅影响展示；条目 `extra_values` 始终是两个字符串，隐藏值不丢失。清单1–200项，text及每附加字段最多2000字符；完成时间有时区，仅已完成项可填写，省略时记录导入时间。
- `link_keys`、`target_keys` 和 Markdown 引用均使用文件内 key，支持前向和循环引用，禁止自身／重复／缺失目标。代码片段内的引用原文不改写。旧非知识条目关系在迁移时保留。
- 资料至少有摘录或实际图片。attachments 元素含 asset_key、caption、alt_text、creator_name；每卡最多10张。图片资产只通过 ZIP 导入；不会联网下载来源或 Markdown 图片。
- ZIP 根目录为 `manifest.json`，格式与JSON相同；仅允许已声明的 `media/<key>.png|jpg|webp` 原图成员。assets 含 key、path、sha256（小写64位）、bytes、mime_type。共享原图仅一份；缩略图在目标重建。拒绝缺图、坏图、重复成员、链接、目录穿越、加密或额外成员。
- `export_info` 包含 generated_at、scope、card_count、excluded，描述此次完整导出，不改变目标账号身份。

## 使用和 API

“我的”页面选择 JSON 或 ZIP → 预检 → 确认导入。只预检不会保存业务数据。字段错误含 card_key、path、code、message。整个批次成功或失败，不会只保存前半部分。

登录后使用 POST `/api/card-transfer/validate` multipart file，取得 digest；再 POST `/api/card-transfer/import`，提交同一 file、expected_digest 和 UUID batch_id。写请求使用当前登录Cookie、可信Origin和X-CSRF-Token。相同账号、batch_id和语义内容重试返回原映射；同键不同内容409。JSON空白／对象键顺序不影响摘要，数组顺序影响。预检后改动文件必须重新预检。重新选文件即新批次，相同内容将创建副本，不按标题去重。

GET `/api/card-transfer/export?format=zip` 导出本人全部卡片，或无图片时选 format=json；有图片选JSON会提示改用ZIP，不静默省略。导出快照一致，图片校验后才提供成功文件。返回包含文件内键到新身份的 mapping、item_mapping、asset_mapping 及数量。401表示需登录，403表示来源／CSRF失败，409表示冲突或需要ZIP，413/422表示限制或内容无效，503表示媒体不可用。

## 限制与恢复

单包最多2000张卡，JSON最多32 MiB，ZIP压缩与解压总量各512 MiB、成员最多10001个；单图最多20 MiB，且受实例媒体配置像素和字节限制。超限完整导出失败，不会截断为部分备份；v1暂不支持分卷。空账号可以导出空cards数组。

网络失败可保持同一文件／批次重试。媒体先以不可变文件发布，数据库整体提交；失败的尝试文件由运维目录 `transfer-<账号与批次摘要前32位>.json` 跟踪，同批次重试仅清理该次未登记文件，不删除现有ready原图。进程中断后需同批次重试；不重试的孤立尝试保留供维护者核对，不能当作成功备份。不要手工删除ready图片。

全站恢复仍使用数据库与媒体联合备份流程。下载文件含私人内容，请妥善保存。

维护者更新交换模型或本目录文档后，在apps/api目录运行 `uv run python -m app.card_transfer_docs` 同步公开Schema和随API交付的副本，再运行 `uv run pytest tests/test_card_package.py -q`。
