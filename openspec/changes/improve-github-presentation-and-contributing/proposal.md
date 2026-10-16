## Why

README已具备产品、演示和运行说明，仓库也已有自动CI，但缺少可直接查看的当前界面截图、贡献指引及结构化反馈入口。用户要求完善GitHub展示与协作，并明确选择Apache-2.0。

## What Changes

- 在README补充真实CI徽章、桌面卡片与手机备忘预览，以及贡献、反馈和许可证入口。
- 从当前代码的独立只读演示生成公开PNG，存入受跟踪的`assets/screenshots/`，记录来源、版本和截图尺寸，继续忽略本机docs及部署资料。
- 添加简短CONTRIBUTING、问题／建议表单及PR模板，链接现有启动、CI和视觉审查说明，避免复制维护命令。
- 使用Apache官方完整文本添加LICENSE，按用户选择声明Apache-2.0及贡献的同许可规则。
- 本轮只准备仓库工件，不修改产品功能、GitHub权限或分支保护，不提交推送、归档或生产发布。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-overview`：增加公开截图、协作入口与许可证要求。

## Impact

涉及README、CONTRIBUTING、LICENSE、`assets/screenshots/`和`.github/`中的协作模板。无应用源码、依赖、锁文件或数据库变化；截图只含项目合成演示内容，不使用真实账号或用户材料。
