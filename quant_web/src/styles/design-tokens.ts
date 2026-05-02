// src/styles/design-tokens.ts
export const tokens = {
  // 色彩 —— 极简科技感，冷灰 + 紫强调
  color: {
    bg: {
      base: '#09090B',          // zinc-950 深色底
      elevated: '#18181B',      // zinc-900 卡片
      overlay: '#27272A80',     // 半透明覆盖层
    },
    accent: {
      primary: '#7C3AED',       // violet-600
      secondary: '#3B82F6',     // blue-500
    },
    text: {
      primary: '#FAFAFA',
      secondary: '#A1A1AA',
      muted: '#52525B',
    }
  },

  // 质感 —— 对应资料“第一层”
  surface: {
    blur: 'backdrop-blur-xl',                    // 玻璃效果
    border: 'border border-white/5',              // 细边框
    shadow: 'shadow-[0_1px_2px_rgba(0,0,0,0.5)]', // 轻阴影
    noise: 'bg-noise',                            // 噪声纹理（需定义CSS class）
  },

  // 动效 —— 对应资料“第二层”，克制、自然
  motion: {
    hover: 'transition-all duration-200 ease-out hover:scale-[1.02]',
    reveal: 'animate-in fade-in slide-in-from-bottom-4 duration-500',
    stagger: 'animate-in fade-in slide-in-from-bottom-4 duration-300 fill-mode-both',
    spring: { type: 'spring', stiffness: 300, damping: 24 },
  },

  // 布局 —— 对应资料“第一层”的bento grid
  layout: {
    grid: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4',
    bento: 'grid grid-cols-4 grid-rows-3 gap-3',  // Bento Grid 仪表盘
    section: 'py-8 px-4 md:px-6 lg:px-8',
  },

  // 圆角 —— 克制，不用大圆角堆叠
  radius: {
    card: 'rounded-lg',        // 8px
    button: 'rounded-md',      // 6px
    modal: 'rounded-xl',       // 12px
  }
};