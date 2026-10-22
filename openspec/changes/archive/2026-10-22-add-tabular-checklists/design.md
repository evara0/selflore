## Context

基线为2554df1，清单是memo/checklist，memo_items以UUID标识行，memo_item_links保留多卡片关系。cards.edit_card将详情合并PATCH，search_text预计算；schema_capability与备份签名负责版本与恢复边界。现有CardForm和MemoEditor分立，CardSources可复用。

## Goals / Non-Goals

目标：稳定行身份及旧接口兼容；共享编辑结构而保留类型内容组件。非目标：新导航、公式、数据库视图、复习状态变更、永久字段删除。

## Decisions

- cards增加memo_columns（三个固定槽位名称）及memo_column_count（显示1–3列）；memo_items增加extra_values（两个固定文本槽位），text继续作为首列，避免复制主文字产生分叉。固定槽位比动态字段ID更适合最多三列的约束。新增SQL检查限制形状、非空列名和长度；旧迁移不改。
- 隐藏只改count，不删除名称或值。PATCH未提交extra_values时按同一行ID合并旧值；提交时允许显式清空。旧响应新增字段，不改变text/target_ids。搜索包含全部槽位（含隐藏值），未完成事项返回列元数据和值。
- 新关联仅接受本人knowledge；已存在非knowledge关联按同一行保留，删除后不能重新添加。服务校验新增集合，不重写旧关系语义。
- 提取共享EditorFrame与类型入口，MemoEditor复用CardSources；CardForm增加固定knowledge的内嵌模式与保存/取消回调。内嵌表单置于父form之外，父组件保持挂载，保留当前行及整张草稿。创建使用已有client_request_id机制；API成功后先关联再刷新，刷新失败不触发重复创建。
- 桌面使用对齐网格表格，移动端每行显示字段名；阅读组件供详情与合集共用。所有新CSS限定在清单/编辑组件内。

## Risks / Trade-offs

- 旧客户端可能看不到附加列 → 服务端按稳定行合并，隐藏值保留，阅读和搜索可恢复。
- 知识已创建但清单未保存 → 明确状态提示，关联保留在草稿，创建不依赖父保存，不自动删除知识。
- 版本回滚 → readiness要求新字段，提升capability；旧程序不能作为支持多列写入的回滚目标；恢复使用完整数据库备份及对应程序。

## Migration Plan

仅新增0008，默认旧清单显示单列且extra_values为空。应用前备份完整数据库；本任务仅在自有6179/6180一次性环境演练，不连接6171或生产。保留迁移历史校验与整库备份签名，不新增独立表。无自动降级或删列。

## Validation Matrix

| 影响面 | 验证 |
| --- | --- |
| 持久化与兼容 | 旧单列、三列重载、隐藏恢复、旧PATCH保值、迁移链 |
| 关联 | 既有异类保留、新入口仅knowledge、创建/取消/失败重试、详情跳转 |
| 清单操作 | 勾选、排序、首列必填、搜索附加值、统一标签 |
| 展示 | 编辑/详情320、390、1280；知识内嵌与失败代表宽度；其他共享编辑代表页面 |
| 回归 | 稳定版本完整适用前后端自动回归一次；问题修复只补相关范围 |
