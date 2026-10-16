## Why

移动端品牌与构建者组分为上下两行，额外撑高页头。用户澄清要求整个构建者组与品牌同一行，组内恢复图标在上、署名在下。

## What Changes

- 手机品牌与整个构建者组横向同行，组内恢复双图标在上、Produced by Evara 在下。
- 保留桌面布局、链接、44 像素点击区域、动效及账号分区。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `default-ui-theme`：移动端品牌与构建者组整体同行。

## Impact

仅调整 apps/web/src/App.css 的手机样式，无依赖或业务逻辑修改。
