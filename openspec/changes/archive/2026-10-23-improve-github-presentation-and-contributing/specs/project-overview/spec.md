## ADDED Requirements

### Requirement: 可公开查看的界面预览

README SHALL 展示桌面卡片与手机备忘的实际应用截图，标明合成演示数据及开发版本边界，并保留在线演示入口。截图及其来源说明 MUST 随仓库交付，MUST NOT 包含真实账号、用户内容或部署接入信息。

#### Scenario: 首次浏览GitHub首页
- **WHEN** 访客阅读README
- **THEN** 访客 SHALL 能直接看到桌面与手机界面，并找到演示链接和截图来源说明

### Requirement: 贡献与反馈入口

项目 SHALL 提供贡献指南、问题与建议模板及PR模板，说明最小复现信息、改动说明、验证证据和评审流程。指南 SHALL 链接已有启动、隔离测试、CI、OpenSpec及视觉审查说明，MUST NOT 把维护者私有部署资料作为贡献前提。自动CI与人工视觉审查的覆盖边界 MUST 明确区分。

#### Scenario: 提交问题或改进建议
- **WHEN** 协作者准备新建Issue或PR
- **THEN** 仓库 SHALL 提供对应模板，指导描述问题、预期和验证情况，并允许说明未执行或不适用的检查

### Requirement: 明确的项目许可

仓库 SHALL 提供完整且未改写的Apache License 2.0官方许可证文本，并从README和贡献指南提供入口。贡献指南 SHALL 说明有意提交的贡献按Apache-2.0提供；第三方材料 SHALL 保留各自许可，不将运行时用户内容声明为项目开源授权范围。

#### Scenario: 了解使用及贡献条款
- **WHEN** 访客准备复用代码或提交贡献
- **THEN** 访客 SHALL 能找到Apache-2.0完整条款及贡献许可说明
