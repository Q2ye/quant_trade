---
name: frontend-craft
description: 量化交易平台前端质感与动效开发技能。涉及页面视觉、CSS质感、动效、3D背景、Naive UI组件使用时调用。
---

# Frontend Craft — 量化平台前端质感开发

> **规范索引**：
> - 页面设计方案生成 → 同目录 `page-design.md`
> - 组件 Props/Emits 接口标准 → 同目录 `component-dev.md`
> - 整体前端开发流程（三阶段）→ `.claude/rules/frontend.md`

## 核心原则
- 所有页面强制使用 `design-tokens.ts` 定义的 Token，禁止硬编码样式。
- 视觉实现遵循「四层分层」：CSS质感 → 动效 → 3D背景 → 组件系统。
- 3D元素仅作背景氛围，不遮挡数据。动效使用 duration-200/300，不做夸张弹跳。

## 四层分层实现清单

### 第一层：CSS质感
- 全局背景：`bg-gradient-mesh` + `bg-noise`（定义于 `global.scss`）
- Naive UI 主题覆写：通过 `src/assets/themes/naive-theme.ts` 的 `getThemeOverrides()` 统一控制色彩、圆角、阴影、字体
- 卡片与面板：依赖 Naive UI `n-card` + 全局 `--n-border-color` / `--n-box-shadow-1` 变量，不额外手写边框/阴影

### 第二层：动效
- 使用 Naive UI 内置 `n-collapse`、`n-modal`、`n-drawer` 的默认过渡（已调优 0.3s `cubic-bezier`）
- 卡片入场：用 Vue `<TransitionGroup>` + `design-tokens.ts` 的 `motion.stagger` 实现错落动画
- 交互反馈：按钮/卡片 hover 用 Naive UI `--n-bezier` 变量，统一 `transition: all 0.2s var(--n-bezier)`
- 数值变化：CSS `transition: all 0.3s ease-out`，用于 `n-statistic` 数值跳动

### 第三层：3D背景
- 仅使用 `components/three/ParticleBackground.vue`（1000粒子，纯装饰）
- 粒子属性：`color="#06B6D4"`（匹配 `design-tokens.ts` accent.primary），`size=0.02`，`opacity=0.4`
- 层级：`fixed inset-0 -z-10`，不参与文档流
- 不创建复杂模型

### 第四层：组件系统
- 统一使用 **Naive UI** 组件（全局已注册，见 `main.ts`）
- 每个信息卡片必须覆盖 Loading / Empty / Error / Data 四种状态
- 图标统一使用 `@iconify/vue` 的 `<Icon>` 组件 + `SmartIcon` 封装

## 状态覆盖模板

每个数据卡片/面板必须按以下结构实现四种状态：

```vue
<template>
  <n-card>
    <!-- Loading 态 -->
    <n-skeleton v-if="loading" :text="true" :repeat="3" />
    
    <!-- Error 态 -->
    <n-result
      v-else-if="error"
      status="500"
      title="数据加载失败"
      description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="retry">重试</n-button>
      </template>
    </n-result>

    <!-- Empty 态 -->
    <n-empty v-else-if="isEmpty" description="暂无数据">
      <template #extra>
        <n-button size="small" @click="onCreate">新建</n-button>
      </template>
    </n-empty>

    <!-- Data 态 -->
    <div v-else>
      <!-- 实际数据展示内容 -->
    </div>
  </n-card>
</template>
```

### 关键 Naive UI 组件用途映射

| 场景 | 组件 | 用法要点 |
|:---|:---|:---|
| 数据卡片 | `n-card` | `title` slot + `header-extra` slot，与 `n-statistic` 搭配 |
| 表格 | `n-data-table` | `virtual-scroll`、`remote` 分页、`row-props` |
| 表单 | `n-form` + `n-form-item` | `:rules` 内置验证，`label-placement="left"` |
| 数值展示 | `n-statistic` | `tabular-nums` 字体等宽 |
| 对话框 | `n-modal` | `preset="dialog"` 用于确认操作 |
| 抽屉 | `n-drawer` | 策略编辑、详情面板 |
| 通知 | `useMessage()` | 操作反馈（成功/失败/警告） |
| 确认 | `useDialog()` | 危险操作二次确认 |
| 加载 | `n-spin` | 全屏/区域加载，`description` 自定义文字 |
| 进度 | `n-progress` | 同步任务、回测进度 |
| 日期 | `n-date-picker` | 回测区间选择、数据同步时间配置 |

### Naive UI 主题变量引用

```scss
// 在 <style scoped lang="scss"> 中使用 Naive UI 暴露的 CSS 变量：
.custom-element {
  color: var(--n-text-color-1);          // 主文本
  color: var(--n-text-color-3);          // 弱文本 / 辅助信息
  background: var(--n-card-color);       // 卡片背景
  border-color: var(--n-border-color);   // 边框
  transition: all 0.2s var(--n-bezier);  // Naive UI 标准贝塞尔曲线
}

// 颜色系统（已在 _variables.scss 中映射）：
// $primary-color、$success-color、$warning-color、$error-color
```

## 禁止项
- 禁止使用 Naive UI 以外的 UI 库组件（Element Plus / Ant Design Vue 一律禁用）
- 禁止硬编码颜色值——必须通过 Naive UI CSS 变量或 `design-tokens.ts` 引用
- 禁止大圆角堆叠（卡片 `border-radius: var(--n-border-radius)`，默认 6px）
- 禁止发光边框、Emoji 图标
- 禁止信息密度过高——单个卡片指标数 ≤ 6 个
- 禁止跳过状态覆盖——每个卡片/面板必须覆盖 Loading/Empty/Error/Data 四种状态
- 禁止直接 import `element-plus` 或 `ant-design-vue` 的任何模块
