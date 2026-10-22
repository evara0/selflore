## Context

动机见 proposal.md。本 worktree HEAD 与指定 `20d52e53165d2df3759a3b9e2b9843a90b2ec0e5` 一致，无继承的未提交修改。

已检查的实现约束：

- `apps/web/src/components/Selectors.tsx` 的 TaxonomyFields 分两次加载 topics/tags；知识／资料分类单选，观点主题多选，备忘仅标签。`features/cards/{CardForm,MemoEditor,Cards,Detail,Memos}.tsx` 与 `features/knowledge/Review.tsx` 各自使用旧字段／URL；Memos 当前无标签筛选，Review 使用页面 `topic` 转API `topic_id`。`lib/demo.ts` 也模拟旧模型，需同步。
- `schemas/workspace.py` 创建限制topic_ids 10、tag_ids 20；知识／资料主题最多1，备忘禁止主题。`routers/workspace.py` 对名称做NFKC/trim，topics最长80、tags最长32，名称冲突409、被引用删除409。`services/cards.py` 分开校验、写入两类关联，筛选单值主题与标签为AND；列表序列化同时返回topics/tags及ID。`services/reviews.py` 直接查询card_topics；`services/memos.py` 的事项分页需要在服务端按父卡片过滤。
- 0002建立带owner复合外键的topics/card_topics、tags/card_tags，主题按kind唯一；0005/0006扩展资料／备忘。`db_migrate.py` 校验不可变历史、持锁并按版本事务提交和授权，不能修改历史SQL。当前应用权限为业务表DML，隔离依赖会话owner条件和数据库复合外键，不能把管理员视为个人数据读取者。
- `test_workspace_integration.py::test_topics_tags_and_safe_delete` 明确断言旧知识多分类失败，必须调整为新模型并独立保留兼容测试；`test_workspace_edges.py` 覆盖无效关系，另有reference/memo迁移及隔离演练测试。视觉流程见根AGENTS.md和 `apps/api/WORKSPACE_TESTING.md`。

现行card-library的单分类要求与目标冲突，已以MODIFIED完整替换；memo-cards的“不得强制标签”仍成立。合集和复习调度契约不变，复习标签过滤只是候选范围变化。

## Goals / Non-Goals

**Goals:** 一个可追溯且同账号唯一的标签模型、可逆向核验的无损关系迁移、明确旧协议适配与恢复门禁。

**Non-Goals:** 不新增类型、层级、导航、自动推断标签或自动内容转换；不改变合集顺序、复习评分、备忘完成语义；本次不删除旧接口或历史来源表，不执行上线。

## Decisions

### 1. 沿用tags/card_tags作为规范模型

扩宽tags.name至80并新增独立规范键；Python API及迁移使用同一明确的NFKC+strip规则，数据库唯一约束为(owner_id,normalized_name)。不折叠大小写、不压缩内部空白，避免推断语义同义词。迁移前扫描全部名称：规范后空或超80、坏外键、单卡去重后超过30则报告并停止，禁止截断。新API默认0至30标签，重复ID拒绝422；同账号重名409附既有ID以支持选用，重命名碰撞仍409。数据库层增加每卡上限的事务边界约束和复合所有者外键，防止直接DML绕过。

不采用新建第三套taxonomy模型，减少持久双写。旧topics/card_topics保留为历史快照，不作为新读写源；应用角色撤销其写权限，兼容层写来源关系。资料／知识的旧单选索引留在快照表不会限制规范关系。

### 2. 映射、来源与确定性去重

追加下一版本（当前链后建议0007_unified_card_tags.sql，实施时确认序号未占用）。增加持久映射 `(owner_id, source_type, old_id) -> canonical_tag_id`，source_type为topic/tag，记录旧kind、原名称及旧创建时间。规范ID优先选组内已有tag的最早created_at、UUID字典序打破并列；没有tag则选最早topic的UUID，若与任何已有tag UUID冲突则在迁移中分配新UUID并持久记录。保留未被引用的标签／主题，不只迁移active内容；同组所有旧ID都有映射。规范显示名称采用获选项的规范名称，原始拼写留在来源记录。

增加关系来源表 `(owner_id,card_id,canonical_tag_id,source_type,source_id)`，旧关系分别标记legacy_topic/legacy_tag及原ID；新统一写入标记unified且source_id为canonical ID。card_tags是全部有效来源的去重投影，事务内维护，复合外键约束两端owner。保留合并前被淘汰的tag行及关系的归档快照后，才删除重复规范行并加入唯一键。快照／映射只授予必要读取，应用不得任意篡改迁移来源；兼容关系更新经限定服务逻辑完成，不授予DDL。

核验不是只比较合并后行数：每条旧关系必须通过映射命中同owner/card的规范关系；反向检查迁移新增关系均有旧来源；按owner报告来源条数、规范条数、合并组、孤儿、生命周期及类型计数。迁移不改变卡片revision/updated_at、creation_request_digest、review状态或任何其他业务ID；避免制造编辑／学习活动。Python只读预检输出指纹与分组报告；SQL迁移持有原表排他锁，在同一事务内重新规范化并生成临时映射、回填和核验，避免使用过期扫描。Python与PostgreSQL规范化规则通过包含Unicode空白的等价测试固定。

### 3. API的显式统一模式与兼容分区

新卡片请求携带 `taxonomy_mode: unified` 与tag_ids，响应tag_ids/tags始终为完整规范集合，并包含taxonomy_mode；新模式topic_ids非空或显式提交旧分区字段为422。新统一PATCH仅在tag_ids出现时替换整套来源为unified；缺失标签字段不修改标签。旧请求缺少模式，tag_ids按旧tag来源解析，topic_ids按旧topic来源解析；创建取两分区并集，PATCH只替换显式出现的来源分区，保留其他旧分区与unified来源。同一个规范关系可有多个来源，移除一个来源不会误删其他来源。旧客户端读完整tags后回写可产生legacy_tag来源，但不能扩大所有者权限或丢标签；超限依然原子拒绝。旧响应topics仅由当前legacy_topic来源投影，并保留原kind；备忘旧请求仍不接收topic_ids，新的备忘使用unified模式。

旧 `/topics` GET按旧kind列来源别名及原ID，POST保留kind校验但创建／复用规范标签并建立别名，PATCH将目标规范标签整体重命名（所有别名展示同步，历史原名不变），DELETE在规范标签任何生命周期被引用时409，否则删除规范标签并将所有别名标为不可用。GET /tags输出规范集合；/tags/{old-id}先查本人映射，PATCH/DELETE都作用于规范对象。禁止别名失效后复用旧ID；不存在和他人ID统一404。旧kind仅兼容边界，新UI不暴露。弃用响应头及操作说明列明替代协议，旧接口删除另行规划。

保留原幂等请求摘要及协议版本：先按旧摘要规则判断已有client_request_id的原载荷重试，再适配标签；不得对已保存摘要批量重算。新增请求摘要按协议模式固定规范，分别测试字段缺省／空数组及迁移前重试。新旧客户端均沿用expected_revision、事务、CSRF和会话所有者。

### 4. 多选查询、URL与复习

新API `/cards`、`/reviews/queue`、`/memo-items` 接收重复参数 `tag_ids=<uuid>&tag_ids=<uuid>&tag_match=all|any`（最多30不同ID，重复归一，未知模式422）；URL同样编码，固定排序以便刷新／后退。all使用关联存在计数或多个EXISTS，any使用EXISTS，避免JOIN使卡片／复习单元重复；先验证全部ID属本人，否则统一404。标签间按模式匹配，其他条件AND。memo-items筛选父卡片后再分页、计数；复习仍只取有效knowledge单元，顺序与额度不变。

旧API topic_id/tag_id与新参数混用拒绝422，防止含糊优先级；页面URL同时携带tag_ids与旧topic/tag时原样转交全部条件并显示相同错误，不默默丢弃旧条件。两个旧参数一起则维持AND。旧topic ID约束映射自带kind，即使规范标签跨类型也不扩大旧范围；旧tag跨类型。页面兼容Cards当前topic/tag、type、state、bookmarked、card、q、sort、lifecycle、offset及Review的topic，保留详情弹层和返回状态；API仍保留kind/kinds、processing_state等字段。将旧topic转换成规范tag条件同时带原类型范围，冲突类型返回空集而不是丢条件，offset重置。无法解析的旧链接显示不可用和清除筛选动作，不默默显示全部。用路由构造器测试固定上述旧参数拼写及浏览器前进后退。

标签使用数全账号active去重卡片数，编辑器明确标注含备忘；页面筛选结果total按页面自身类型范围计数，事项数为条目、复习数为单元，不能混用。索引保留(owner,tag,card)和(owner,card,tag)，以规模测试验证all/any查询计划和稳定分页。

### 5. 前端统一控件与状态

重构TaxonomyFields为同一TagSelector，四类编辑器共用：标签名搜索、已选chip、移除、0/30计数、无结果与内联创建；按Enter选择明确高亮项，Escape关闭建议，焦点可返回触发控件，达到上限仍允许取消。加载／创建失败独立反馈，重复创建选用已有项，切换类型不清标签。快速收录默认不选，保留手改及失败后保存能力。

Account设置中的TaxonomySettings改为单一标签管理，支持创建、重命名、删除并明确全账号使用数和使用中保护；移除topics管理切换。Cards、Memos及Review在现有筛选区复用多选控件和全部／任一切换、清空，筛选改变归零offset，保留搜索及其他条件；未完成事项按父清单标签。列表和详情移除分类栏，保留类型标识并统一渲染标签；长名称换行，空标签仅在编辑器说明“可稍后整理”，不标“未分类”。演示数据和离线查询使用同语义及数量；现有合集中的卡片显示也需核对共享标签渲染，无新增入口。

## Risks / Trade-offs

- [规范化导致同名合并、长主题超旧32限制] → 80字符上限、原名快照、确定性映射与逐关系核验；不做语义去重。
- [旧PATCH覆盖新关系] → 来源分区、显式unified模式和混合客户端测试；代价是过渡期保留来源元数据。
- [旧链接因跨类型合并扩大范围] → 保留topic原kind并测试冲突组合。
- [旧包能启动但读写不完整] → 新结构能力标记、readiness及发布回退检查，不能仅依赖原reference/memo能力相同。
- [停写窗口与大库回填锁] → 在隔离副本量测扫描、回填、索引及锁等待；维护窗口预算不足则不迁移，不在线冒险重跑。
- [恢复快照丢失上线后写入] → 优先兼容前向修复；恢复整库须停写、保存故障库副本并由人工确认数据截点及补录方案。

## Migration Plan

1. 在一次性6179实例演练从0006含两账号、三种topic、tags、同名／全角名、长名、30关联、未使用项、归档回收站及清单升级；另从空库走完整链比较约束／授权。记录指纹、计数及逐关系核验，失败注入、重跑、并发迁移与越权DML均覆盖。
2. 预先构建配套前后端，声明新的统一标签结构能力，扩展启动readiness／发布兼容检查；不改旧迁移校验和。准备同能力的可恢复包。操作文档列出精确包、目标库、版本链、备份ID及人工批准点，正式上线属于后续另行授权操作。
3. 上线时暂停旧应用及其他写入来源，做完整数据库备份并在隔离库验证恢复（媒体依现有联合备份流程保留）；预检报告由操作者核对。通过既有迁移命令以migrator角色执行新版本，DDL、映射／来源回填、授权、核验与版本记录同事务提交。启动不自动迁移。
4. 迁移失败不激活，核对事务已回滚后恢复旧包。迁移成功只激活统一标签能力包，核验readiness、两账号隔离、四类型保存、多选筛选、旧链接／旧请求及既有复习和清单后再开放写入。
5. 激活失败禁止自动切回0006旧包，使用相同能力的上一包或前向修复；需要恢复备份时停写、保全故障库、明确截点及上线后写入恢复计划，在隔离库演练并验证后人工切换，禁止DROP新表或逆向压回单分类。保留映射／快照至独立清理变更批准，不在此次上线删除。

实施已另获授权；仅在当前worktree及一次性隔离环境执行，不运行生产发布。实施验收必须分别记录自动测试、截图生成、截图实际查看、视觉结论、修复与复测及未覆盖范围。
