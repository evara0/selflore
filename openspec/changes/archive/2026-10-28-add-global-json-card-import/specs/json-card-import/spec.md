## ADDED Requirements

### Requirement: 全局 JSON 导入入口

系统 SHALL 从全局新建流程提供独立的 JSON 导入入口，允许登录用户选择 UTF-8 文件或粘贴 JSON，不要求预先选择卡片类别。kind SHALL 决定资料、事实知识、观点或备忘类别，form 和 memo_format SHALL 决定其有效形式；首版每份输入 SHALL 只创建一张卡片。

#### Scenario: 从全局新建导入三列清单
- **WHEN** 用户通过全局新建进入 JSON 导入并输入 kind=memo、memo_format=checklist 的内容
- **THEN** 系统 SHALL 自动识别为清单，保留三个列名、条目文字、额外字段和说明，不要求进入备忘编辑器选择导入

### Requirement: 无持久化校验与预览

系统 SHALL 在用户确认保存之前校验和预览内容，MUST NOT 因选文件、粘贴或预览而创建卡片。输入限制 SHALL 为 1 MiB UTF-8；非法 JSON、重复键、非对象、未知字段、无效类别及不满足既有卡片规则的内容 MUST 显示具体错误，MUST NOT 静默回退类别或忽略字段。缺少 ID 的清单条目 SHALL 自动生成稳定 UUID。预览接口 SHALL 使用既有登录、Origin 及 CSRF 保护。

#### Scenario: JSON 缺少类别
- **WHEN** 用户预览没有 kind 的对象
- **THEN** 系统 SHALL 指出类别字段错误，保留输入且不写入卡片

#### Scenario: 清单预览完整
- **WHEN** 用户预览带有三列、说明和十一行需求的有效清单
- **THEN** 系统 SHALL 显示类别、标题、说明、全部行与列值，默认未提供完成状态的条目为未完成

### Requirement: 确认保存与失败重试

系统 SHALL 在显式确认后使用现有创建卡片接口保存，并在成功后进入对应类别详情。相同草稿重试 SHALL 使用相同 client_request_id 及条目 ID；失败 SHALL 保留输入、预览与可重试状态。修改输入 MUST 使既有预览失效；未保存离开 SHALL 提示，成功后 SHALL 解除保护。标签、附件及关联对象 SHALL 沿用现有账号归属检查。

#### Scenario: 保存临时失败
- **WHEN** 有效预览首次保存失败后用户再次保存
- **THEN** 系统 SHALL 保留草稿并沿用相同请求载荷重试，成功后只进入实际创建的详情

#### Scenario: 预览后修改 JSON
- **WHEN** 用户修改已预览的 JSON
- **THEN** 系统 SHALL 清除可保存的旧预览，要求重新校验，MUST NOT 保存旧内容
