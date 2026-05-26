/*
 * Design Tokens —— 唯一设计 Token 定义
 *
 * 颜色值源自 naive-theme.ts（唯一颜色源），通过 injectThemeCSSVariables() 注入
 * 的 --color-* CSS 变量引用。surface/motion/layout 使用 global.scss 中的 CSS 工具类。
 *
 * 使用方式：
 *   import { tokens } from '@/styles/design-tokens'
 *   <div :class="tokens.surface.glass">...</div>
 *   <div :style="{ color: tokens.color.accent.primary }">...</div>
 */
export const tokens = {
  // 色彩 —— 映射到 --color-* CSS 变量（injectThemeCSSVariables 注入）
  color: {
    bg: {
      base: "var(--color-bg-primary, #080C16)",
      elevated: "var(--color-bg-card, rgba(12, 18, 32, 0.55))",
      overlay: "var(--depth-deepest, #040810)",
    },
    accent: {
      primary: "var(--color-primary, #448AFF)",
      secondary: "var(--color-primary, #448AFF)",
    },
    text: {
      primary: "var(--color-text-primary, #EBEDF5)",
      secondary: "var(--color-text-secondary, #8898B8)",
      muted: "var(--color-text-tertiary, rgba(136, 152, 184, 0.6))",
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

  // 圆角 — Naive UI 注入的少数有效 --n-* 变量之一
  radius: {
    card: "var(--n-border-radius, 6px)",
    button: "var(--n-border-radius, 6px)",
    modal: "var(--n-border-radius, 6px)",
  },
} as const;

/*
 * 配套 CSS 工具类 —— 定义在 styles/global.scss 的"设计Token CSS落地层"区段。
 *
 * .glass-surface { backdrop-filter: blur(16px); background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.05); }
 * .card-surface  { background: var(--color-bg-card, #12122A); border: 1px solid var(--color-border, #1E1E4A); border-radius: var(--n-border-radius, 6px); box-shadow: var(--box-shadow-1, 0 0 1px rgba(0, 255, 200, 0.08)); }
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
