## Context

这是首个前端组件，范围限于视觉外壳。

## Goals / Non-Goals

**Goals:** Vite + pnpm + TypeScript + 原生 CSS，实现默认单主题网格布局。

**Non-Goals:** 不复制参考站的内容、交互或品牌；不实现数据、认证、API 或多主题。

## Decisions

使用 `apps/web/`、React 状态切换占位导航、CSS `linear-gradient` 绘制网格、半透明 `backdrop-filter` 面板；自定义文字标识为 “Lattice / SELFLORE”。

## Risks / Trade-offs

- [玻璃效果浏览器差异] → 保留半透明背景色作为降级。
- [小屏导航拥挤] → 使用可换行或横向滚动的导航布局。
