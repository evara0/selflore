## Why

现有Vitest与Playwright能够验证功能、部分溢出和对比度，但截图生成后没有统一的查看要求，文字偏移、局部裁切和间距问题仍会漏检。需要将真实浏览器样式审查作为前端变更的完成条件，并区分自动测试、截图生成和实际查看的结果。

## What Changes

- 新增项目根AGENTS.md，规定视觉审查触发范围、影响面、失败反馈与完成标准。
- 在openspec/config.yaml增加tasks规划规则和apply指导，要求前端变更生成具体视觉验收任务；无展示影响时说明不适用原因。
- 在既有测试说明中补齐视口、状态、合成数据、截图查看清单、复测和证据报告模板。
- 使用当前页面抽样演练并记录发现与未覆盖范围，不顺带修改业务样式。
- 不增加Evals、Skill、Hook、截图基准比较、依赖或发布门禁；不改变产品功能或操作日常数据库。

## Capabilities

### New Capabilities

- `frontend-visual-review`: 项目工程验收流程，定义前端变更的真实浏览器截图查看及证据要求。

### Modified Capabilities

无。沿用default-ui-theme的产品视觉要求，新规范只规定如何验收，不改变主题设计。

## Impact

持久实施文件仅为AGENTS.md、openspec/config.yaml、apps/api/WORKSPACE_TESTING.md；另增加本变更的规划及验收记录。沿用现有Playwright和浏览器，审查产物进入忽略缓存目录。现有备忘与构建者署名变更保持原样。
