## Why

当前前端实测中，说明文字与超大标题重叠，内容面板的占位文字也过于接近边界，削弱了参考布局的清晰层级。

## What Changes

- 调整首页标题区的间距、最大字号与说明文字定位。
- 调整半透明面板内占位文字的字号和留白。
- 保持现有网格、导航、默认主题、品牌和端口不变。

## Capabilities

### New Capabilities

- `web-shell-visual-hierarchy`: 前端布局在常见桌面和窄屏尺寸保持清晰、无重叠的视觉层级。

### Modified Capabilities

- 无。

## Impact

仅影响 `apps/web/` 样式与布局结构；不改变页面内容、导航行为、依赖或服务接口。
