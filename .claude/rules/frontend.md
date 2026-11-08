---
paths: "quant_web/**"
---

# 前端页面开发规则

> 样式系统与组件规范见 `.claude/skills/frontend-craft/SKILL.md` 及子文件。

## S2 设计阶段：《页面设计方案》

> 前端**不是独立流程**：S2 的产物由《设计》换成《页面设计方案》，S3 起与后端一致。
> 阶段划分、四档、退回规则见 `docs/06-标准规范/00_交付流程总纲.md`；本文件只管「前端方案怎么写」。

**必须先输出方案，确认前严禁编码。** 详细规范见 `.claude/skills/frontend-craft/page-design.md`。

方案必须包含：

- 页面类型推断：仪表盘(Bento 4列) / 列表(筛选+表格) / 表单(单列居中640px) / 详情(摘要+Tab)
- 路由与数据来源（接口 / store / 事件）
- ASCII 布局图 + 各区域说明
- 状态覆盖：Loading / Empty / Error / 权限不足
- 全局背景：`bg-gradient-mesh` + `bg-noise`，导航栏 `glass-surface`；仪表盘/详情页可选 `ParticleBackground`，列表/表单页禁用 3D

> **涉及 `core/` 或 `shared/` → 必须列出所有受影响模块**（自动升 T2，见总纲 §二）。

## 编码规范

- 页面 → `views/{Module}/`，组件 → `components/{module}/`，逻辑 → `composables/`
- SCSS 变量和混入已由 vite 自动注入，组件中直接使用无需 import
- 每个卡片必须覆盖四种状态：Loading(`n-skeleton`) / Empty(`n-empty`) / Error(`n-result` + 重试) / Data
- 图标使用 `@iconify/vue` 的 `<Icon>` 组件

## 禁止项

- **严禁**硬编码颜色值 — 必须通过 Naive UI CSS 变量或 `design-tokens.ts` 引用
- **严禁**使用 Naive UI 以外的 UI 库（Element Plus / Ant Design Vue）
- **严禁**跳过状态覆盖
- **严禁**跳过 S2《页面设计方案》确认直接编码
- **严禁**修改规划外文件或顺手重构无关代码
- **严禁**涉及 `styles/` 或 `naive-theme.ts` 的修改不经全局影响评估

## 验证清单

- [ ] 页面路由可访问，API 数据正确渲染
- [ ] Loading / Empty / Error / Data 四状态各自验证
- [ ] 响应式：手机(<768px) / 平板(768-1024px) / 桌面(>1024px)
- [ ] 首屏 <2s，3D 帧率 >30fps（如使用）

## 异常处理

遇到以下情况必须暂停并提交用户确认（与总纲 §六一致）：
- **方案偏差**：设计方案无法落地 → 写《偏差说明》，追加到 `03-任务.md`「偏差记录」
- **需求变更**：用户中途修改需求 → 改 `01-需求.md` 的 AC，并在「判据变更」记时间与理由
- **跨模块影响**：需改 `styles/`、`naive-theme.ts` 或后端 `core/`/`shared/` 但未在设计中列出 → 回 S2 补影响面，改档为 T2 后重新确认

**严禁自行假设解决方案或跳过确认步骤。**
