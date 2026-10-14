## Why

当前页面没有项目构建者的外部入口。用户要求以两个有动画的图标提供 GitHub 仓库和个人博客链接，保持刚精简的界面表达。

## What Changes

- 桌面构建者组位于左上品牌右侧及页脚右侧；手机在品牌下方独立一行，署名位于图标下方。
- GitHub 图标链接到 https://github.com/evara0/selflore，博客图标链接到 https://evara.blog/。
- 恢复紫色发散线条品牌标志与 favicon；游客隐藏页头登录，登录后保留账号设置入口。
- 使用克制的悬停、键盘焦点及触控反馈，支持减少动态效果偏好。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `default-ui-theme`：允许页脚构建者入口并定义链接可达性和动效边界。

## Impact

仅影响前端壳层、图标组件和样式，无 API、依赖和数据变化。不提交、归档或部署。
