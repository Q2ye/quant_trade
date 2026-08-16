---
paths: "quant_web/**"
---

# 前端页面开发规则

> 样式系统与组件规范见 `.claude/skills/frontend-craft/SKILL.md` 及子文件。

## 三阶段开发流程

### 阶段 0：输出《页面设计方案》

**必须先输出方案，确认前严禁编码。** 详细规范见 `.claude/skills/frontend-craft/page-design.md`。

速查：
- 页面类型推断：仪表盘(Bento 4列) / 列表(筛选+表格) / 表单(单列居中640px) / 详情(摘要+Tab)
- 全局背景：`bg-gradient-mesh` + `bg-noise`，导航栏 `glass-surface`
- 必须输出：页面类型、路由、数据来源、ASCII 布局图、各区域说明、状态覆盖
- 仪表盘/详情页可选 `ParticleBackground`，列表/表单页禁用 3D

### 阶段 1：输出《前端开发路径说明》

方案确认后输出：涉及文件 + 跨模块影响 + 四层实施计划 + 后端依赖 + 验证方案。

> **涉及 `core/` 或 `shared/` → 必须列出所有受影响模块**

### 阶段 2：实施开发与验证

确认后编码。

## 编码规范

- 页面 → `views/{Module}/`，组件 → `components/{module}/`，逻辑 → `composables/`
- SCSS 变量和混入已由 vite 自动注入，组件中直接使用无需 import
- 每个卡片必须覆盖四种状态：Loading(`n-skeleton`) / Empty(`n-empty`) / Error(`n-result` + 重试) / Data
- 图标使用 `@iconify/vue` 的 `<Icon>` 组件

## 禁止项

- **严禁**硬编码颜色值 — 必须通过 Naive UI CSS 变量或 `design-tokens.ts` 引用
- **严禁**使用 Naive UI 以外的 UI 库（Element Plus / Ant Design Vue）
- **严禁**跳过状态覆盖
- **严禁**跳过阶段 0/1 直接编码
- **严禁**修改规划外文件或顺手重构无关代码
- **严禁**涉及 `styles/` 或 `naive-theme.ts` 的修改不经全局影响评估

## 验证清单

- [ ] 页面路由可访问，API 数据正确渲染
- [ ] Loading / Empty / Error / Data 四状态各自验证
- [ ] 响应式：手机(<768px) / 平板(768-1024px) / 桌面(>1024px)
- [ ] 首屏 <2s，3D 帧率 >30fps（如使用）

## 异常处理

遇到以下情况必须暂停并提交用户确认：
- **方案偏差**：设计方案无法落地 → 提交《偏差分析与修正计划》
- **需求变更**：用户中途修改需求 → 提交《需求变更影响评估》
- **跨模块影响**：需修改 `styles/`、`naive-theme.ts` 或后端 `core/`/`shared/` 但未在阶段 1 规划中 → 更新开发路径说明重新确认

**严禁自行假设解决方案或跳过确认步骤。**
