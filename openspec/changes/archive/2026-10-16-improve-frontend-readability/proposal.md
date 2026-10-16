## Why

前端页面将多段逻辑及JSX压缩为长行，统一卡片页仍名为Knowledge，已退出生产路由的Opinions页仅由旧测试导入。用户要求整理可读性，降低审阅和维护成本，同时保持现有功能和布局。

## What Changes

- 固定Prettier开发依赖与前端格式配置，统一src下TypeScript／TSX和前端配置格式，并提供format及format:check；CI增加格式检查。
- 统一列表迁至`features/cards/Cards.tsx`，旧Opinions用例改为验证实际统一列表与旧URL兼容后删除无生产入口的旧页。
- 按稳定职责拆分App的认证弹窗、页面框架与路由，以及Editor中的卡片表单、来源区域和合集编辑器；保持组件状态生命周期、DOM、类名、URL、请求及文案。
- 用现有组件测试、相关浏览器回归、构建和格式检查验证，生成整理前后代表页面截图，实际查看整理后截图并检查交互。
- 不部署、自动归档、提交或推送。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。仅内部重构与工程格式化，不改变产品行为契约，声明skip_specs。

## Impact

影响apps/web源文件、开发依赖与锁文件、CI格式步骤及对应说明。保持CSS、数据库、后端、运行依赖和公开界面不变；旧入口兼容继续保留。
