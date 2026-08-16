---
name: component-dev
description: 量化平台前端组件开发规范。约束通用组件和图表组件的接口、样式、状态与主题，确保全平台一致性。
globs: quant_web/src/components/**
---

# 组件开发规范

> **与现有规范的关系**：
> - 本规范定义组件的 Props/Emits 接口契约和开发流程，是 `.claude/skills/frontend-craft/SKILL.md` 四层分层中「第四层：组件系统」的细化。
> - 页面设计方案生成见同目录 `page-design.md`，整体前端开发流程见 `.claude/rules/frontend.md`。
> - 颜色与样式 Token 以 `src/assets/themes/naive-theme.ts`（唯一颜色源）和 `src/styles/design-tokens.ts` 为准。

## 核心原则
- 所有组件必须在 `src/components/` 下按功能域分子目录。
- 强制使用 `design-tokens` 绑定样式，禁止硬编码颜色/阴影/圆角。
- 每个组件必须覆盖 Loading / Empty / Error / Data 四种状态。

## 通用组件规范（MetricCard, DataTable 等）
- **Props 标准**：必须包含 `loading: boolean`, `error: string | null`, `data: any`, `emptyText?: string`。
- **Emits 标准**：必须包含 `retry` 事件。
- **Slot 暴露**：提供 `default` 插槽用于自定义内容区，`actions` 插槽用于操作按钮。
- **样式**：使用 `tokens.surface.card` 作为容器 class，内部文字使用项目全局工具类（`.text-primary` / `.text-secondary` / `.text-muted`）或 Naive UI CSS 变量（`var(--n-text-color-1)` / `var(--n-text-color-3)`）。

## 图表组件规范（ChartCard 等）
- **图表库**：统一使用 Apache ECharts 5.x。
- **主题注入**：图表颜色随 Naive UI 深色/浅色主题自动适配，通过 `src/plugins/echarts.ts` 注入全局 `$echarts` 实例。图表配色引用 `naive-theme.ts` 中 `THEME_CONSTANTS` 的语义色（`--n-primary-color`、`--n-success-color` 等），无需单独 `registerTheme`。
- **数据格式**：传入数据遵循 `{ categories: string[], series: { name: string, data: number[] }[] }` 或特定图表类型格式（在组件内转换）。
- **响应式**：必须在 `mounted` 和窗口 `resize` 事件中调用 `chart.resize()`。
- **交互**：tooltip 必须显示，鼠标悬停高亮，支持点击事件向外 emit。
- **禁止项**：禁止 3D 饼图、禁止过强动画（duration > 500ms）、禁止图表内使用渐变填充。

## 开发流程
1. 在 `src/components/` 下创建子文件夹，如 `data/MetricCard.vue`。
2. 实现 Props/Emits 和四状态模板。
3. 在页面中通过 `<MetricCard v-bind="cardProps" @retry="fetchData" />` 使用。