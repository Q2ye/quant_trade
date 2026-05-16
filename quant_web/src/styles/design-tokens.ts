/*
 * Design Tokens —— 唯一设计 Token 定义
 *
 * 颜色值源自 naive-theme.ts（唯一颜色源），通过 Naive UI CSS 变量引用。
 * surface/motion/layout/radius 使用项目已有 SCSS 工具类和 CSS 变量。
 *
 * 使用方式：
 *   import { tokens } from '@/styles/design-tokens'
 *   <div :class="tokens.surface.glass">...</div>
 *   <div :style="{ color: tokens.color.accent.primary }">...</div>
 */
export const tokens = {
  // 色彩 —— 映射到 Naive UI CSS 变量（naive-theme.ts 注入）
  color: {
    bg: {
      base: "var(--n-body-color)",
      elevated: "var(--n-card-color)",
      overlay: "var(--n-color-modal)",
    },
    accent: {
      primary: "var(--n-primary-color)",
      secondary: "var(--n-primary-color-hover)",
    },
    text: {
      primary: "var(--n-text-color-1)",
      secondary: "var(--n-text-color-2)",
      muted: "var(--n-text-color-3)",
    },
  },

  // 质感 —— 玻璃态、卡片、噪声
  surface: {
    glass: "glass-surface",
    card: "card-surface",
    noise: "bg-noise",
    mesh: "bg-gradient-mesh",
  },

  // 动效 —— 搭配 Naive UI --n-bezier 使用
  motion: {
    hover: "hover-lift",
    stagger: "stagger-item",
  },

  // 布局
  layout: {
    grid2: "grid-2col",
    grid4: "grid-4col",
    section: "section-pad",
    bento: "bento-grid",
  },

  // 圆角
  radius: {
    card: "var(--n-border-radius)",
    button: "var(--n-border-radius)",
    modal: "var(--n-border-radius)",
  },
} as const;

/*
 * 配套 CSS 工具类 —— 定义在 styles/global.scss 的"设计Token CSS落地层"区段。
 *
 * .glass-surface { backdrop-filter: blur(16px); background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.05); }
 * .card-surface  { background: var(--n-card-color); border: 1px solid var(--n-border-color); border-radius: var(--n-border-radius); box-shadow: var(--n-box-shadow-1); }
 * .hover-lift    { transition: all 0.2s var(--n-bezier); }
 * .hover-lift:hover { transform: scale(1.02); }
 * .stagger-item  { animation: fadeInUp 0.3s ease both; }
 * .bento-grid    { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
 * .grid-2col     { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
 * .grid-4col     { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
 * .section-pad   { padding: 32px 16px; }
 * @media (min-width: 768px) { .section-pad { padding: 32px 24px; } }
 * @media (min-width: 1024px) { .section-pad { padding: 32px 32px; } }
 *
 * @keyframes fadeInUp {
 *   from { opacity: 0; transform: translateY(12px); }
 *   to   { opacity: 1; transform: translateY(0); }
 * }
 */
