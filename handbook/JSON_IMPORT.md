# JSON 卡片导入

从全局“新建”进入“JSON 导入”，选择文件或粘贴内容，点击“校验并预览”，核对后再“确认导入”。导入入口独立于具体类别，由 JSON 中的 kind 自动识别目标。需要登录；预览不会创建卡片，成功后打开对应详情。

## 支持范围

每次一张卡片，输入是 JSON 对象，UTF-8 编码，最大 1 MiB，可带 BOM。暂不支持数组批量导入、合集、更新已有卡片或数据库备份恢复。未知字段及重复键会报错，不静默丢弃。

| 类别／形式 | 必需内容 |
| --- | --- |
| 资料卡 | kind=reference、title，body_md 原始摘录或有效的已有附件 |
| 问答知识 | kind=knowledge、form=qa、title、question_md、answer_md |
| 填空知识 | kind=knowledge、form=cloze、title、body_md（有效填空语法） |
| 观点 | kind=opinion、title、body_md |
| 普通备忘 | kind=memo、memo_format=note、title，body_md 可选 |
| 清单 | kind=memo、memo_format=checklist、title、非空 memo_items |

字段名和内容限制沿用[工作区 API](../apps/api/WORKSPACE_API.md)。类别不会由文件名或当前页面推断。不要填写 owner_id、顶层 id、revision 或 client_request_id；账号来自当前会话，新卡片和请求 ID 由系统生成。

## 三字段清单

下面是一份可直接使用的最小对象；行 ID 可省略，预览时自动补齐。

```json
{
  "kind": "memo",
  "memo_format": "checklist",
  "title": "论文阅读工具需求",
  "body_md": "先验收安卓阅读、悬浮翻译和术语记录。",
  "memo_columns": ["项目", "需求说明", "优先级／状态"],
  "memo_column_count": 3,
  "memo_items": [
    {"text": "安卓端", "extra_values": ["手机直接阅读，方便续读", "必须"]},
    {"text": "术语记录", "extra_values": ["保存英文词、解释、原句和论文出处", "必须"]}
  ]
}
```

完整的[安卓论文阅读工具需求示例](../apps/web/public/examples/paper-reading-checklist.json)包含十一行、三列，以及目标、理想流程、三个待定细节和首轮验收要求。导入页也提供下载。

- memo_columns 始终为三个列名；memo_column_count 指定显示 1–3 列。
- 每行 text 为第一列，extra_values 为第二和第三列，必须是两个文本；省略时默认为两个空值。
- 一张清单最多 200 行，每个单元格最多 2000 字符。is_completed 默认 false，“必须”“已明确”等优先级文字不会自动变成完成状态。
- 预览会列出隐藏的字段，保存后按显示列数呈现，隐藏值仍保留。

## 附加信息和失败处理

可填写 note_md（仅资料卡）、来源字段、tag_ids 及适用的附件／清单关联。标签、附件和关联卡片的 ID 必须可由当前账号使用，保存时按现有规则检查；不会根据名称创建标签或下载远程图片。跨账号或其他实例的 ID 不能当作可移植文件引用。

问答、正文和说明支持现有安全 Markdown。导入不是自动解析任意 Markdown 表格，需要先转换为上述 JSON。选择文件或预览后仍需明确确认保存。

预览错误保留原输入；修改 JSON 后需重新预览。保存失败会保留预览和请求 ID，直接重试可沿用幂等创建；不要为重试反复修改并重新导入同一份内容。当前草稿只保留在页面，未保存离开会提示，刷新或关闭后不能保证恢复。

## 接口与验证

POST /api/cards/import-preview 接受 `{"json_text":"JSON 原文"}`，返回标准化 CardContent，无持久化。登录、Origin 与 CSRF 要求同其他写接口。确认保存仍使用 POST /api/cards，补上页面生成的 client_request_id；规范和限制统一见[API 说明](../apps/api/WORKSPACE_API.md)。

浏览器契约回归见[仅前端替身回归](../apps/api/WORKSPACE_TESTING.md#仅前端替身回归)。测试调用真实预览校验，但创建保留在内存，不作为业务数据库写入验收。
