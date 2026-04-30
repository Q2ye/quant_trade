---
globs: "quant-web/**"
---
# 前端页面开发规则

> 本文件在处理 `quant-web/**` 前端路径时自动加载。

## 三阶段开发流程

### 阶段 0：自动生成页面设计方案

当用户提出页面需求时，**必须先输出《页面设计方案》**，方案确认前禁止编写任何代码。

#### 页面类型自动推断
| 类型 | 关键词 | 默认布局 |
| :--- | :--- | :--- |
| 仪表盘 | 驾驶舱、面板、仪表盘、监控、Dashboard、总览 | Bento Grid 4列 |
| 列表页 | 列表、查询、搜索、管理 | 筛选区(280px) + 表格(flex-1) |
| 表单页 | 新建、编辑、配置、设置 | 单列居中(max-w-640px) |
| 详情页 | 详情、查看、报告 | 顶部摘要 + 下部分栏 |

#### 布局与质感自动分配
- **仪表盘**：4 列 Bento Grid，核心指标占 2 列，次要占 1 列。用粒子场背景。卡片 stagger 出现。
- **列表页**：顶部搜索 + 左侧筛选 + 右侧表格 + 底部分页。无 3D 背景。用 scroll reveal。
- **表单页**：分组，每组标题分隔。无 3D。焦点字段用 hover feedback。
- **详情页**：顶部 Key-Value 摘要卡片，下部分 Tab。可选粒子场。
- **全局**：所有页面 bg-gradient-mesh + bg-noise，玻璃导航栏，shadcn-vue 组件。

#### 数据源自动映射
根据模块从 `docs/` 和 `api/routers/` 查找对应 API。找不到则标注「待确认」提问。

#### 设计方案输出模板（必须严格遵循）
```markdown
## 页面设计方案：[页面名称]

### 页面类型
[仪表盘 / 列表 / 表单 / 详情]

### 所属模块与路由
- 模块：[模块名]
- 路由：/[module]/[page]

### 数据来源
| 数据项 | 来源 | 方式 |
| :--- | :--- | :--- |
| [描述] | /api/xxx | GET / WebSocket |

### 区域布局（ASCII 图）
┌──────────────────────┬──────────┐
│  A (宽)              │  B       │
├──────────┬───────────┼──────────┤
│  C       │  D        │  E       │
└──────────┴───────────┴──────────┘

### 各区域详细说明
- **A. [名称]**：内容，数据源，交互行为
- **B. [名称]**：...
- ...

### 质感与氛围
- 背景：[粒子场 / 纯渐网格]
- 卡片：[玻璃质感 / 普通]
- 动效：[stagger / scroll-reveal / hover-feedback]

### 状态覆盖
- Loading：骨架屏描述
- Empty：空状态文案
- Error：错误提示与重试
- 特殊状态：阈值告警等
```

> 阶段 0（页面设计方案）已作为前置步骤完成，设计方案经用户确认后进入阶段1。


## 阶段 1：输出前端开发路径说明

设计方案确认后，同时加载 `skills/quantsys-architect.md` 和 `skills/frontend-craft.md`，输出《前端开发路径说明》。

### 需加载的技能

| 技能 | 用途 |
| :--- | :--- |
| `quantsys-architect` | 确认 API 路由、WebSocket 事件、数据表结构 |
| `frontend-craft` | 确认四层分层规范、组件使用方式、禁止项 |

### 输出格式

```markdown
## 前端开发路径说明

### 涉及文件
**新增文件：**
- `pages/xxx/XxxPage.vue` — 页面主文件
- `components/xxx/XxxCard.vue` — 对应区域卡片组件
- `composables/useXxx.ts` — 数据获取与状态管理（如有）

**修改文件：**
- `api/routers/xxx_router.py` — 新增 API 端点（如有需要）
- `core/events/xxx_events.py` — 新增事件类型（如有需要）
- `shared/database/repositories/xxx_repo.py` — 新增查询方法（如有需要）

### 跨模块影响评估
- 对 `api/` 的修改将影响前端哪些页面？
- 对 `core/` 的修改将影响哪些订阅该事件的引擎？
- 对 `shared/` 的修改会被哪些 Service 调用？

### 四层分层实施计划
**第一层 — CSS 质感：**
- 背景：`bg-gradient-mesh` + `bg-noise`
- 导航：`glass` Class（`backdrop-blur-lg` + `bg-white/5` + `border-white/5`）
- 卡片：`card-surface` Class（`bg-zinc-900` + `border-white/5` + `rounded-lg` + `shadow-sm`）
- 引用方式：`import { tokens } from '@/styles/design-tokens'`

**第二层 — 动效：**
- 使用 `motion-v` 实现
- 卡片入场：`stagger` 错落动画，delay 0.08s
- 交互反馈：`hover feedback`（`whileHover={{ scale: 1.02 }}`，duration 0.2s）
- 数值变化：CSS `transition: all 0.3s ease-out`

**第三层 — 3D 背景：**
- [ ] 使用 `components/three/ParticleBackground.vue`
- [ ] 不使用 3D（列表页/表单页）
- 若使用：1000 粒子，`color="#7C3AED"`，`size=0.02`，`opacity=0.4`，定位 `fixed inset-0 -z-10`

**第四层 — 组件系统：**
- 统一使用 shadcn-vue：`Card` `Button` `Badge` `Progress` `Skeleton` `Toast`
- 每个卡片必须覆盖四种状态：Loading / Empty / Error / Data

### 后端依赖
- 需新增的 API：[列出或标注“无”]
- 需订阅的 WebSocket 事件：[列出或标注“无”]
- 是否需要数据库变更：[是 / 否]

### 验证方案
| 检查项 | 标准 |
| :--- | :--- |
| 响应式 | 手机(<768px) / 平板(768-1024px) / 桌面(>1024px) 三种布局皆可用 |
| 状态覆盖 | 每个卡片单独验证 Loading / Empty / Error / Data 四种状态 |
| 性能 | 3D 帧率 >30fps（如使用），首屏加载 <2s |
| 组件一致性 | 所有交互组件来自 shadcn-vue，无自定义样式覆盖 |
```

**关键铁律**：
- 如果修改涉及 `core/` 或 `shared/` 目录，**必须**在《开发路径说明》中单独列出受影响的所有模块，并给出同步修改计划。
- **严禁**跳过此步骤直接开始编码。必须等待用户回复“确认”后进入阶段 2。

## 阶段 2：实施开发与验证

用户确认《前端开发路径说明》后，按以下规范编码。

### 编码规范

**目录结构：**
```text
src/
├── pages/{module}/
│ └── XxxPage.vue
├── components/
│ ├── {module}/
│ │ └── XxxCard.vue
│ └── three/
│ └── ParticleBackground.vue
├── composables/
│ └── useXxx.ts
└── styles/
└── design-tokens.ts
```

**基类与依赖：**
- 所有页面组件放在 `pages/{module}/` 下，路由在 `router/` 中注册
- 可复用卡片组件放在 `components/{module}/` 下
- 数据获取逻辑封装在 `composables/` 中

**设计 Token 引用：**
```vue  
    import { tokens } from '@/styles/design-tokens'
    
    // 导航栏
    <nav :class="tokens.surface.glass">...</nav>
    
    // 卡片
    <div :class="tokens.surface.card">...</div>
    
    // 按钮 hover
    <Button :class="tokens.motion.hover">操作</Button>
```

**状态覆盖（每个卡片必须实现）：**
```vue
<template>
  <Card>
    <Skeleton v-if="loading" class="h-24 w-full" />
    
    <div v-else-if="error" class="flex flex-col items-center gap-2 py-8">
      <p class="text-zinc-400">数据加载失败</p>
      <Button variant="outline" size="sm" @click="retry">重试</Button>
    </div>
    
    <div v-else-if="isEmpty" class="flex flex-col items-center gap-2 py-8">
      <p class="text-zinc-500">暂无数据</p>
    </div>
    
    <div v-else>
      <!-- 数据展示 -->
    </div>
  </Card>
</template>
```
**修改禁区：**
- 只修改《前端开发路径说明》中列出的文件
- 禁止顺手重构无关代码或修改其他页面样式

### 验证交付 
代码完成后输出验证清单：

## 验证清单

### 功能验证
- [ ] 页面路由可正常访问：`http://localhost:5173/{route}`
- [ ] API 调用返回数据并在页面正确渲染
- [ ] WebSocket 事件实时推送并更新界面（如适用）

### 状态验证
- [ ] Loading：刷新页面，每个卡片先显示 Skeleton
- [ ] Empty：清空数据源，每个卡片显示空状态文案
- [ ] Error：断开 API，每个卡片显示错误提示 + 重试按钮
- [ ] Data：正常数据展示正确

### 响应式验证
- [ ] 手机宽度(<768px)：布局为单列，导航折叠
- [ ] 平板宽度(768-1024px)：布局为 2 列
- [ ] 桌面宽度(>1024px)：布局为完整 Bento Grid / 多列

### 性能验证
- [ ] 首屏加载时间 <2s（Chrome DevTools Lighthouse）
- [ ] 3D 粒子保持 >30fps（如使用，Chrome DevTools FPS Meter）
- [ ] 动效无卡顿、无闪烁

### 运行命令
```bash
npm run dev          # 启动开发服务器
npm run build        # 构建验证
npm run lint         # 代码规范检查
```

**异常处理**
-开发过程中遇到以下情况必须暂停并提交用户确认：
-方案偏差：实现中发现设计方案无法落地 → 提交《偏差分析与修正计划》
- 需求变更：用户中途提出与原方案不同的修改 → 提交《需求变更影响评估》
- 跨模块影响：需要修改 core/ shared/ 的文件未在阶段 1 规划中 → 更新《前端开发路径说明》并重新确认

### 禁止自行假设解决方案或跳过确认步骤。