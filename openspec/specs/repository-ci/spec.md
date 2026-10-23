# repository-ci Specification

## Purpose

让每次仓库推送与PR能够自动复跑公开的基础检查，给协作者提供明确的文档、前端和后端结果；通过隔离测试资源、失败即停止以及保留报告，避免把跳过测试、缺少环境或仅本机发布能力误认为仓库持续集成已经成功。

## Requirements

### Requirement: 自动触发与最小权限

仓库 SHALL 在分支push、pull_request和手动请求时运行CI；CI MUST 使用只读仓库权限和固定Action提交，不获取生产凭据或执行部署。同一上下文的新运行 SHALL 取消过时运行。

#### Scenario: 更新分支或PR
- **WHEN** 协作者推送分支或更新PR
- **THEN** CI SHALL 自动提供文档、前端和后端独立检查结果

#### Scenario: 外部贡献
- **WHEN** PR来自fork
- **THEN** 检查 MUST 不依赖生产Secrets，不运行具有生产访问能力的本机发布工具

### Requirement: 复用公开检查并如实失败

CI SHALL 冻结安装依赖，运行前端Lint、组件测试及类型／构建检查；后端 SHALL 运行公开pytest。命令失败、后端失败／跳过／空测试报告 MUST 阻止该检查通过，不得用continue-on-error掩盖结果。

#### Scenario: 后端环境不完整
- **WHEN** pytest返回成功但存在skip或零测试
- **THEN** 后端检查 MUST 失败并保留报告以定位缺失环境

### Requirement: 自有一次性数据库

后端CI MUST 仅创建仓库缓存中的专用PostgreSQL 18实例，沿用6179与6180隔离边界，拒绝占用端口和链接路径。实例 SHALL 只监听回环；完成或失败后 MUST 停止所属实例，不操作开发或生产数据库。

#### Scenario: 端口已占用
- **WHEN** 所需端口已由其他进程占用
- **THEN** 辅助脚本 MUST 在初始化前失败，不停止占用者

#### Scenario: 测试失败
- **WHEN** 初始化或测试中途异常
- **THEN** 脚本 SHALL 尝试停止本次创建的所有实例并返回失败，保留报告及缓存供排查

### Requirement: 当前公开文档检查

CI SHALL 检查随Git交付的当前公开Markdown的本地链接和章节锚点。被忽略／未跟踪的资料、缺失目标或越出仓库的目标 MUST 失败；代码块中的链接示例不得误报。历史OpenSpec工件与外站可用性不属于该检查范围。

#### Scenario: 说明链接断裂
- **WHEN** 当前文档引用已删除文件或不存在章节
- **THEN** 文档检查 SHALL 返回非零并指出来源与目标

### Requirement: 可复跑及覆盖边界

项目 SHALL 记录CI入口、运行方式、报告位置及未覆盖范围。CI结果 MUST 区分本地验证与实际GitHub运行；浏览器E2E、人工视觉审查、生产备份及发布不能因基础CI通过而视为完成。

#### Scenario: 查看成功检查
- **WHEN** 维护者查看CI结果
- **THEN** 文档 SHALL 说明三类基础检查的覆盖，明确不代表视觉或生产验收成功
