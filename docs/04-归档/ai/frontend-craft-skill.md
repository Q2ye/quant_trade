---
name: frontend-craft
description: 量化交易平台前端质感与动效开发技能。涉及页面视觉、CSS质感、动效、3D背景、shadcn组件使用时调用。
---

# Frontend Craft — 量化平台前端质感开发

## 核心原则
- 所有页面强制使用 design-tokens.ts 定义的 Token，禁止硬编码样式。
- 视觉实现遵循「四层分层」：CSS质感 → 动效 → 3D背景 → 组件系统。
- 3D元素仅作背景氛围，不遮挡数据。动效使用 duration-200/300，不做夸张弹跳。

## 四层分层实现清单
### 第一层：CSS质感
- 全局背景：`bg-gradient-mesh` + `bg-noise`
- 导航和浮动卡片：`backdrop-blur-xl` + `border-white/5` + `shadow`

### 第二层：动效
- 使用 `motion-v` 实现 hover feedback、scroll reveal、stagger animation
- 数值变化用 CSS transition `duration-300 ease-out`

### 第三层：3D背景
- 仅使用 TresJS ParticleBackground（1000粒子，纯装饰）
- 不创建复杂模型

### 第四层：组件系统
- 统一使用 shadcn-vue 组件
- 每个信息卡片必须覆盖 Loading / Empty / Error / Data 四种状态

## 状态覆盖模板
（提供具体代码片段）

## 禁止项
- 禁止大圆角堆叠（max radius lg）
- 禁止发光边框、Emoji 图标
- 禁止信息密度过高