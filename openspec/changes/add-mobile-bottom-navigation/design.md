## Context

参考样式以底部图标导航承担移动端页面切换。

## Goals / Non-Goals

**Goals:** 固定底部导航、中心新建动作、保留品牌。

**Non-Goals:** 不实现真实新建功能。

## Decisions

复用现有页面状态，在移动端以 CSS 隐藏顶部 nav，并显示 bottom nav。

## Risks / Trade-offs

- [底部遮挡内容] → 为主区域预留底部安全空间。
