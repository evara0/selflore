## Context

见proposal。App同时持有会话与认证表单状态、导航和所有路由；Editor导出合集编辑器并包含完整卡片表单。现有67项Vitest覆盖认证、游客、备忘、资料及工作区，浏览器测试已有本地替身与隔离库约定。

## Goals / Non-Goals

**Goals:** 分离可机械核对的排版与命名／职责修改，留下可持续执行的格式入口。

**Non-Goals:** 不设计新状态框架，不统一所有表单为抽象schema，不改CSS、接口、文案或历史URL，不借重构修复其他产品问题。

## Decisions

- Prettier固定3.9.10，100列、单引号、无分号、LF；只覆盖src的TS／TSX及根TS配置，避免无关CSS、资产与浏览器测试的大范围diff。限定的.gitattributes规则使这些文件在Windows的core.autocrlf=true下仍检出为LF，避免格式检查误报。既有Oxlint负责规则，Prettier负责格式；CI通过format:check阻止重新压缩。
- 先保存基线构建及代表截图，然后机械格式化；使用TypeScript打印器规范化AST对比，单独识别需要人工核对的格式语义差异。
- Cards迁移保留Flashcard、筛选参数、卡片类型记忆及复习入口；Review仍属于knowledge。Opinions生产无导入，只在工作区测试使用，测试转到Cards并保留URL选中内容、反向链接与无学习操作断言。旧`/opinions`重定向由App路由测试覆盖。
- App保留会话与认证控制状态，提取受控AuthDialog、WorkspaceLayout和WorkspaceRoutes。组件定义在模块顶层，保持Suspense的key、保护路由、缓存清理、打开／关闭及请求时机，避免提取导致重挂载。
- Editor保留按id／kind的key路由选择；CardForm独立文件，组织与来源为受控CardSources组件；CollectionEditor归入collections目录。保持DOM层级及提交payload，不引入新的状态归属。
- 浏览器替身使用原生合成演示：四主页、卡片详情、编辑页、认证弹窗在320、390、1280检查。保存前后首屏及末尾证据、实际查看整理后图像，核对页尾可达与键盘；行为测试覆盖真正可能受组件拆分影响的认证、保存与旧URL。

## Risks / Trade-offs

- [格式diff较大] → 先机械格式再拆分，记录AST核对；不手改无关页面逻辑。
- [提取组件改变状态／空白] → 保留key与DOM，测试状态切换及序列化结构，并比较前后截图。
- [本机替身不能代替真实API] → 本轮不改API形状，用现有前端测试和浏览器替身核对UI／请求，报告明确未重复后端验证及未覆盖真实设备。
