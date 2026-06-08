// themes/naive-theme.ts
// 职责：唯一主题源 - 包含所有颜色常量、CSS变量生成、Naive UI主题配置
// ============================================================================

import type { GlobalThemeOverrides } from "naive-ui";

// ============================================================================
// 主题常量定义 - 唯一颜色源（深色/浅色主题）
// ============================================================================

/**
 * 主题常量配置 - 作为整个应用的唯一颜色源
 * 包含深色和浅色主题的所有颜色、字体、阴影、圆角等变量
 */
const THEME_CONSTANTS = {
  // 深色主题变量 - 深海蓝 (Deep Ocean) — Bloomberg 经典机构风
  DARK: {
    // 基础色彩 — 深海蓝黑底 + 蓝色主色
    PRIMARY_BG: "#080C16", // 主背景色（深海黑）
    SECONDARY_BG: "rgba(10, 14, 24, 0.50)", // 次背景色（蓝调半透明）
    ACCENT_COLOR: "#448AFF", // 强调色/主色调（深海蓝）
    TEXT_PRIMARY: "#EBEDF5", // 主要文字颜色（冷白）
    TEXT_SECONDARY: "#8898B8", // 次要文字颜色（蓝灰）
    BORDER_COLOR: "rgba(25, 35, 60, 0.50)", // 边框颜色（蓝调低对比）
    DISABLED_BG: "#4A5A78", // 禁用状态背景色

    // 语义化颜色 - 用于状态提示
    SUCCESS_COLOR: "#00E676", // 成功状态颜色（绿）
    WARNING_COLOR: "#FFB74D", // 警告状态颜色（暖橙）
    DANGER_COLOR: "#FF5252", // 危险/错误状态颜色（红）
    INFO_COLOR: "#40C4FF", // 信息状态颜色（浅蓝）
    PURPLE_COLOR: "#7C6FF7", // 辅助色（紫罗兰点缀）

    // 组件颜色 - 特定组件的背景色（半透明玻璃态，透出 3D 粒子）
    CARD_BG: "rgba(12, 18, 32, 0.72)", // 卡片背景色（深海蓝半透明）
    CARD_HEADER_BG: "rgba(16, 24, 42, 0.78)", // 卡片头部背景色
    TOOLBAR_BG: "rgba(8, 12, 22, 0.72)", // 工具栏背景色
    SIDEBAR_BG: "rgba(6, 10, 18, 0.82)", // 侧边栏背景色
    INPUT_BG: "rgba(8, 12, 22, 0.55)", // 输入框背景色
    HOVER_BG: "rgba(68, 138, 255, 0.05)", // 悬停状态背景色（蓝光微闪）
    ACTIVE_BG: "rgba(68, 138, 255, 0.10)", // 激活状态背景色
    POPOVER_BG: "rgba(18, 26, 46, 0.94)", // 弹窗背景色（高不透明，确保文字清晰可读）
    MODAL_BG: "rgba(12, 18, 32, 0.95)", // 模态框背景色（近实色，避免底层内容穿透）

    // 股票状态颜色 - 量化交易专用（A股红涨绿跌）
    STOCK_UP_COLOR: "#FF5252", // 股票上涨颜色（红）
    STOCK_DOWN_COLOR: "#00E676", // 股票下跌颜色（绿）
    STOCK_FLAT_COLOR: "#8898B8", // 股票持平颜色（蓝灰）

    // 状态指示颜色 - 用于进度、时间等状态
    STATUS_RUNNING: "#448AFF", // 运行中状态颜色（深海蓝）
    STATUS_PROGRESS: "#00E676", // 进行中状态颜色（绿）
    STATUS_TIME: "#FFB74D", // 时间相关状态颜色（暖橙）
    STATUS_REMAINING: "#FF5252", // 剩余/紧张状态颜色（红）

    // 阴影系统 - 蓝色荧光
    CARD_SHADOW: "0 0 1px rgba(68, 138, 255, 0.06)", // 卡片微发光
    CARD_HOVER_SHADOW: "0 0 2px rgba(68, 138, 255, 0.12)", // 卡片悬停微发光
    HOVER_SHADOW: "0 0 2px rgba(68, 138, 255, 0.08)", // 通用悬停微发光

    // 字体系统
    FONT_FAMILY: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", // 现代无衬线
    FONT_SIZE_BASE: "11.2px", // 基础字体大小

    // 圆角系统 - 专业级，适中圆润
    BORDER_RADIUS: "6px", // 标准圆角
    BORDER_RADIUS_SM: "4px", // 小圆角
    BORDER_RADIUS_LG: "8px", // 大圆角

    // ====================================================================
    // P0: 图表多线色板 — ECharts 多策略/多指标对比用
    // ====================================================================
    CHART_PALETTE: [
      "#448AFF", // C1 深海蓝 — 主线/策略A
      "#40C4FF", // C2 浅蓝 — 策略B/次线
      "#7C6FF7", // C3 紫罗兰 — 策略C
      "#FF6B9D", // C4 霓虹粉 — 策略D
      "#00E676", // C5 绿 — 基准线
      "#FFB74D", // C6 暖橙 — 策略E
      "#FF5252", // C7 红 — 策略F
      "#C0D0E8", // C8 冰蓝白 — 均值/参考线
    ],

    // ====================================================================
    // P1: 背景深度层级 — UI 层次感（深度递增）
    // ====================================================================
    DEPTH: {
      DEEPEST: "rgba(4, 8, 16, 0.92)", // 最深底（模态遮罩）
      PAGE:    "#080C16", // 页面底色（保持不透明）
      RAISED:  "rgba(8, 12, 22, 0.60)", // 悬浮面板
      CARD:    "rgba(12, 18, 32, 0.55)", // 卡片表面
      HEADER:  "rgba(16, 24, 42, 0.65)", // 卡片头部
      HOVER:   "rgba(20, 30, 52, 0.50)", // 悬停高亮
    },

    // ====================================================================
    // P2: 热力/严重度色阶 — 风控监控、因子强度等连续色阶场景
    // ====================================================================
    SEVERITY_SCALE: {
      CRITICAL: "#D50000", // 严重/超阈值
      HIGH:     "#FF5252", // 高/危险
      MEDIUM:   "#FFB74D", // 中/警告
      LOW:      "#00E676", // 低/安全
      NEUTRAL:  "#8898B8", // 中性/无数据
    },

    // ====================================================================
    // P3: 涨跌配色方案（与上方股票状态色配合，独立定义以支持切换）
    // ====================================================================
    STOCK_SCHEMES: {
      INTERNATIONAL: { up: "#00E676", down: "#FF5252", flat: "#8898B8" },
      ASHARE:        { up: "#FF5252", down: "#00E676", flat: "#8898B8" },
    },

    // ====================================================================
    // P4: 深海渐变对 — Logo、重点区域、进度条等
    // ====================================================================
    GRADIENTS: {
      OCEAN_DEEP: "linear-gradient(135deg, #448AFF 0%, #0D47A1 100%)",
      ICE_BLUE:   "linear-gradient(135deg, #448AFF 0%, #40C4FF 100%)",
      TWILIGHT:   "linear-gradient(135deg, #7C6FF7 0%, #448AFF 100%)",
      BIOLUM:     "linear-gradient(135deg, #40C4FF 0%, #00E676 100%)",
    },
  },

  // 浅色主题变量 - 量化交易专用浅色主题
  LIGHT: {
    // 基础色彩
    PRIMARY_BG: "#FFFFFF", // 主背景色（白色）
    SECONDARY_BG: "#F8F9FA", // 次背景色（浅灰色）
    ACCENT_COLOR: "#2196F3", // 强调色/主色调（品牌色，保持不变）
    TEXT_PRIMARY: "#212529", // 主要文字颜色（深灰色）
    TEXT_SECONDARY: "#6C757D", // 次要文字颜色（中灰色）
    BORDER_COLOR: "#DEE2E6", // 边框颜色（浅灰色）
    DISABLED_BG: "#8B949E", // 禁用状态背景色（保持一致）

    // 语义化颜色
    SUCCESS_COLOR: "#28A745", // 成功状态颜色（绿色）
    WARNING_COLOR: "#FFC107", // 警告状态颜色（黄色）
    DANGER_COLOR: "#DC3545", // 危险/错误状态颜色（红色）
    INFO_COLOR: "#17a2b8", // 信息状态颜色（保持一致）
    PURPLE_COLOR: "#9c27b0", // 紫色辅助色（保持一致）

    // 组件颜色
    CARD_BG: "#FFFFFF", // 卡片背景色（白色）
    CARD_HEADER_BG: "#F8FAFC", // 卡片头部背景色（极浅灰）
    TOOLBAR_BG: "#F8F9FA", // 工具栏背景色（浅灰色）
    SIDEBAR_BG: "#FFFFFF", // 侧边栏背景色（白色）
    INPUT_BG: "#FFFFFF", // 输入框背景色（白色）
    HOVER_BG: "#E9ECEF", // 悬停状态背景色（浅灰色）
    ACTIVE_BG: "#e3fdf8", // 激活状态背景色（浅绿色）

    // 股票状态颜色
    STOCK_UP_COLOR: "#DC3545", // 股票上涨颜色（红色）
    STOCK_DOWN_COLOR: "#28A745", // 股票下跌颜色（绿色）
    STOCK_FLAT_COLOR: "#6C757D", // 股票持平颜色（灰色）

    // 状态指示颜色
    STATUS_RUNNING: "#2196F3", // 运行中状态颜色（保持一致）
    STATUS_PROGRESS: "#28A745", // 进行中状态颜色（绿色）
    STATUS_TIME: "#FFC107", // 时间相关状态颜色（黄色）
    STATUS_REMAINING: "#DC3545", // 剩余/紧张状态颜色（红色）

    // 阴影系统
    CARD_SHADOW: "0 4px 12px rgba(0, 0, 0, 0.08)", // 浅色轻度阴影
    CARD_HOVER_SHADOW: "0 8px 24px rgba(0, 0, 0, 0.12)", // 浅色中度阴影
    HOVER_SHADOW: "0 4px 16px rgba(0, 0, 0, 0.12)", // 浅色悬停阴影

    // 字体系统
    FONT_FAMILY: "'Inter', 'Segoe UI', sans-serif", // 浅色主题字体
    FONT_SIZE_BASE: "11.2px", // 基础字体大小（保持一致）

    // 圆角系统
    BORDER_RADIUS: "4px", // 标准圆角（稍小）
    BORDER_RADIUS_SM: "2px", // 小圆角（更小）
    BORDER_RADIUS_LG: "6px", // 大圆角（稍大）

    // ====================================================================
    // P0: 图表多线色板
    // ====================================================================
    CHART_PALETTE: [
      "#2196F3", "#FF9800", "#4CAF50", "#E91E63",
      "#00BCD4", "#CDDC39", "#FF5722", "#607D8B",
    ],

    // ====================================================================
    // P1: 背景深度层级
    // ====================================================================
    DEPTH: {
      DEEPEST: "rgba(0, 0, 0, 0.50)",
      PAGE:    "#FFFFFF",
      RAISED:  "#F8F9FA",
      CARD:    "#FFFFFF",
      HEADER:  "#F8FAFC",
      HOVER:   "#E9ECEF",
    },

    // ====================================================================
    // P2: 热力/严重度色阶
    // ====================================================================
    SEVERITY_SCALE: {
      CRITICAL: "#D50000",
      HIGH:     "#DC3545",
      MEDIUM:   "#FFC107",
      LOW:      "#28A745",
      NEUTRAL:  "#6C757D",
    },

    // ====================================================================
    // P3: 涨跌配色方案
    // ====================================================================
    STOCK_SCHEMES: {
      INTERNATIONAL: { up: "#28A745", down: "#DC3545", flat: "#6C757D" },
      ASHARE:        { up: "#DC3545", down: "#28A745", flat: "#6C757D" },
    },

    // ====================================================================
    // P4: 渐变
    // ====================================================================
    GRADIENTS: {
      OCEAN_DEEP: "linear-gradient(135deg, #2196F3 0%, #1565C0 100%)",
      ICE_BLUE:   "linear-gradient(135deg, #2196F3 0%, #00BCD4 100%)",
      TWILIGHT:   "linear-gradient(135deg, #9C27B0 0%, #2196F3 100%)",
      BIOLUM:     "linear-gradient(135deg, #00BCD4 0%, #4CAF50 100%)",
    },
  },
} as const;

// ============================================================================
// 辅助函数区域
// ============================================================================

/**
 * 十六进制颜色转RGB颜色字符串
 * @param hex 十六进制颜色值（如#2196F3）
 * @returns RGB颜色字符串（如"33, 150, 243"）
 * @example hexToRgb('#2196F3') => "33, 150, 243"
 */
function hexToRgb(hex: string): string {
  // 移除#号并解析RGB分量
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : "0, 0, 0"; // 解析失败返回黑色
}

/**
 * 生成带透明度的颜色值
 * @param color 基础颜色值（支持十六进制和RGB）
 * @param opacity 透明度（0-1之间）
 * @returns 带透明度的RGBA颜色字符串
 * @example colorWithOpacity('#2196F3', 0.8) => "rgba(33, 150, 243, 0.8)"
 */
const colorWithOpacity = (color: string, opacity: number): string => {
  // 如果是十六进制颜色，转换为RGB
  if (color.startsWith("#")) {
    return `rgba(${hexToRgb(color)}, ${opacity})`;
  }
  // 如果是rgb颜色，转换为rgba
  if (color.startsWith("rgb(")) {
    return color.replace("rgb", "rgba").replace(")", `, ${opacity})`);
  }
  // 默认返回原色
  return color;
};

// ============================================================================
// CSS变量生成函数 - 根据主题生成完整的CSS变量字符串
// ============================================================================

/**
 * 生成主题对应的CSS变量字符串
 * @param isDark 是否为深色主题
 * @returns 包含所有CSS变量定义的字符串
 * @description 将主题常量转换为CSS变量，用于动态注入到页面
 */
export function generateThemeCSSVariables(isDark: boolean): string {
  const theme = isDark ? THEME_CONSTANTS.DARK : THEME_CONSTANTS.LIGHT;
  const textSecondaryRgb = hexToRgb(theme.TEXT_SECONDARY);

  return `
    /* ============================================================================
     * 动态生成的主题CSS变量
     * 主题: ${isDark ? "深色主题 (Dark)" : "浅色主题 (Light)"}
     * 生成时间: ${new Date().toISOString()}
     * ============================================================================ */
    
    :root {
      /* -------------------- 基础颜色变量 -------------------- */
      --color-primary: ${theme.ACCENT_COLOR};                    /* 主色调（品牌色） */
      --color-success: ${theme.SUCCESS_COLOR};                   /* 成功状态颜色 */
      --color-warning: ${theme.WARNING_COLOR};                   /* 警告状态颜色 */
      --color-error: ${theme.DANGER_COLOR};                      /* 错误状态颜色 */
      --color-info: ${theme.INFO_COLOR};                         /* 信息状态颜色 */
      --color-purple: ${theme.PURPLE_COLOR};                     /* 紫色辅助色 */
      
      /* -------------------- 背景颜色变量 -------------------- */
      --color-bg-primary: ${theme.PRIMARY_BG};                   /* 页面主背景色 */
      --color-bg-secondary: ${theme.SECONDARY_BG};               /* 页面次背景色 */
      --color-bg-card: ${theme.CARD_BG};                         /* 卡片背景色 */
      --color-bg-card-header: ${theme.CARD_HEADER_BG};           /* 卡片头部背景色 */
      --color-bg-input: ${theme.INPUT_BG};                       /* 输入框背景色 */
      --color-bg-hover: ${theme.HOVER_BG};                       /* 悬停状态背景色 */
      --color-bg-active: ${theme.ACTIVE_BG};                     /* 激活状态背景色 */
      --color-bg-disabled: ${theme.DISABLED_BG};                 /* 禁用状态背景色 */
      
      /* -------------------- 文字颜色变量 -------------------- */
      --color-text-primary: ${theme.TEXT_PRIMARY};               /* 主要文字颜色 */
      --color-text-secondary: ${theme.TEXT_SECONDARY};           /* 次要文字颜色 */
      --color-text-tertiary: rgba(${textSecondaryRgb}, 0.6);     /* 三级文字颜色（60%透明度） */
      
      /* -------------------- 边框颜色变量 -------------------- */
      --color-border: ${theme.BORDER_COLOR};                     /* 边框颜色 */
      --color-divider: ${theme.BORDER_COLOR};                    /* 分割线颜色 */
      
      /* -------------------- 股票状态颜色变量 -------------------- */
      --color-stock-up: ${theme.STOCK_UP_COLOR};                 /* 股票上涨颜色 */
      --color-stock-down: ${theme.STOCK_DOWN_COLOR};             /* 股票下跌颜色 */
      --color-stock-flat: ${theme.STOCK_FLAT_COLOR};             /* 股票持平颜色 */
      
      /* -------------------- 状态指示颜色变量 -------------------- */
      --color-status-running: ${theme.STATUS_RUNNING};           /* 运行中状态颜色 */
      --color-status-progress: ${theme.STATUS_PROGRESS};         /* 进行中状态颜色 */
      --color-status-time: ${theme.STATUS_TIME};                 /* 时间状态颜色 */
      --color-status-remaining: ${theme.STATUS_REMAINING};       /* 剩余状态颜色 */
      
      /* -------------------- 圆角变量 -------------------- */
      --border-radius: ${theme.BORDER_RADIUS};                   /* 标准圆角 */
      --border-radius-sm: ${theme.BORDER_RADIUS_SM};             /* 小圆角 */
      --border-radius-md: ${theme.BORDER_RADIUS};                /* 中等圆角（同标准） */
      --border-radius-lg: ${theme.BORDER_RADIUS_LG};             /* 大圆角 */
      
      /* -------------------- 阴影变量 -------------------- */
      --box-shadow-1: ${theme.CARD_SHADOW};                      /* 一级阴影（轻度阴影） */
      --box-shadow-2: ${theme.CARD_HOVER_SHADOW};                /* 二级阴影（中度阴影） */
      --box-shadow-3: ${isDark ? "0 0 4px rgba(0, 255, 200, 0.18)" : "0 16px 48px rgba(0, 0, 0, 0.16)"}; /* 三级阴影 */
      
      /* -------------------- 字体变量 -------------------- */
      --font-family: ${theme.FONT_FAMILY};                       /* 主要字体族 */
      --font-family-mono: 'Monaco, "Courier New", monospace';    /* 等宽字体族 */
      --font-size-base: ${theme.FONT_SIZE_BASE};                 /* 基础字体大小 */

      /* -------------------- P0: 图表色板变量 -------------------- */
      --chart-c1: ${theme.CHART_PALETTE[0]}; /* 霓虹青 — 主线 */
      --chart-c2: ${theme.CHART_PALETTE[1]}; /* 紫罗兰 — 策略B */
      --chart-c3: ${theme.CHART_PALETTE[2]}; /* 霓虹粉 — 策略C */
      --chart-c4: ${theme.CHART_PALETTE[3]}; /* 霓虹金 — 策略D */
      --chart-c5: ${theme.CHART_PALETTE[4]}; /* 电光蓝 — 基准线 */
      --chart-c6: ${theme.CHART_PALETTE[5]}; /* 荧光绿 — 策略E */
      --chart-c7: ${theme.CHART_PALETTE[6]}; /* 霓虹橙 — 策略F */
      --chart-c8: ${theme.CHART_PALETTE[7]}; /* 冷白 — 参考线 */

      /* -------------------- P1: 背景深度变量 -------------------- */
      --depth-deepest: ${theme.DEPTH.DEEPEST};
      --depth-page:    ${theme.DEPTH.PAGE};
      --depth-raised:  ${theme.DEPTH.RAISED};
      --depth-card:    ${theme.DEPTH.CARD};
      --depth-header:  ${theme.DEPTH.HEADER};
      --depth-hover:   ${theme.DEPTH.HOVER};

      /* -------------------- P2: 严重度色阶变量 -------------------- */
      --severity-critical: ${theme.SEVERITY_SCALE.CRITICAL};
      --severity-high:     ${theme.SEVERITY_SCALE.HIGH};
      --severity-medium:   ${theme.SEVERITY_SCALE.MEDIUM};
      --severity-low:      ${theme.SEVERITY_SCALE.LOW};
      --severity-neutral:  ${theme.SEVERITY_SCALE.NEUTRAL};

      /* -------------------- P4: 渐变变量 -------------------- */
      --gradient-ocean-deep: ${theme.GRADIENTS.OCEAN_DEEP};
      --gradient-ice-blue:   ${theme.GRADIENTS.ICE_BLUE};
      --gradient-twilight:   ${theme.GRADIENTS.TWILIGHT};
      --gradient-biolum:     ${theme.GRADIENTS.BIOLUM};

      /* -------------------- Naive UI 变量别名桥接 -------------------- *
       * Naive UI 不将主题色注入为全局 --n-* 变量，但项目中 90+ 文件
       * 引用了这些变量名。此处桥接，使所有现有引用自动生效。       */
      --n-text-color-1: ${theme.TEXT_PRIMARY};
      --n-text-color-2: ${theme.TEXT_SECONDARY};
      --n-text-color-3: rgba(${textSecondaryRgb}, 0.6);
      --n-primary-color: ${theme.ACCENT_COLOR};
      --n-primary-color-hover: ${colorWithOpacity(theme.ACCENT_COLOR, 0.8)};
      --n-body-color: ${theme.PRIMARY_BG};
      --n-card-color: ${theme.CARD_BG};
      --n-color-modal: ${theme.SECONDARY_BG};
      --n-border-color: ${theme.BORDER_COLOR};
      --n-box-shadow-1: ${theme.CARD_SHADOW};
      --n-box-shadow-2: ${theme.CARD_HOVER_SHADOW};
    }
    
    /* ============================================================================
     * 主题切换类（向后兼容）
     * 当body有.theme-light类时，应用浅色主题变量
     * 注意：现代实现应使用动态注入，此类仅用于兼容旧代码
     * ============================================================================ */
    
    .theme-light {
      --color-primary: ${THEME_CONSTANTS.LIGHT.ACCENT_COLOR};
      --color-success: ${THEME_CONSTANTS.LIGHT.SUCCESS_COLOR};
      --color-warning: ${THEME_CONSTANTS.LIGHT.WARNING_COLOR};
      --color-error: ${THEME_CONSTANTS.LIGHT.DANGER_COLOR};
      --color-info: ${THEME_CONSTANTS.LIGHT.INFO_COLOR};
      --color-purple: ${THEME_CONSTANTS.LIGHT.PURPLE_COLOR};
      
      --color-bg-primary: ${THEME_CONSTANTS.LIGHT.PRIMARY_BG};
      --color-bg-secondary: ${THEME_CONSTANTS.LIGHT.SECONDARY_BG};
      --color-bg-card: ${THEME_CONSTANTS.LIGHT.CARD_BG};
      --color-bg-card-header: ${THEME_CONSTANTS.LIGHT.CARD_HEADER_BG};
      --color-bg-input: ${THEME_CONSTANTS.LIGHT.INPUT_BG};
      --color-bg-hover: ${THEME_CONSTANTS.LIGHT.HOVER_BG};
      --color-bg-active: ${THEME_CONSTANTS.LIGHT.ACTIVE_BG};
      
      --color-text-primary: ${THEME_CONSTANTS.LIGHT.TEXT_PRIMARY};
      --color-text-secondary: ${THEME_CONSTANTS.LIGHT.TEXT_SECONDARY};
      --color-text-tertiary: rgba(${hexToRgb(THEME_CONSTANTS.LIGHT.TEXT_SECONDARY)}, 0.6);
      
      --color-border: ${THEME_CONSTANTS.LIGHT.BORDER_COLOR};
      --color-divider: ${THEME_CONSTANTS.LIGHT.BORDER_COLOR};
      
      --color-stock-up: ${THEME_CONSTANTS.LIGHT.STOCK_UP_COLOR};
      --color-stock-down: ${THEME_CONSTANTS.LIGHT.STOCK_DOWN_COLOR};
      --color-stock-flat: ${THEME_CONSTANTS.LIGHT.STOCK_FLAT_COLOR};
      
      --border-radius: ${THEME_CONSTANTS.LIGHT.BORDER_RADIUS};
      --border-radius-sm: ${THEME_CONSTANTS.LIGHT.BORDER_RADIUS_SM};
      --border-radius-md: ${THEME_CONSTANTS.LIGHT.BORDER_RADIUS};
      --border-radius-lg: ${THEME_CONSTANTS.LIGHT.BORDER_RADIUS_LG};
      
      --box-shadow-1: ${THEME_CONSTANTS.LIGHT.CARD_SHADOW};
      --box-shadow-2: ${THEME_CONSTANTS.LIGHT.CARD_HOVER_SHADOW};
      --box-shadow-3: 0 16px 48px rgba(0, 0, 0, 0.16);
      
      --font-family: ${THEME_CONSTANTS.LIGHT.FONT_FAMILY};

      --n-text-color-1: ${THEME_CONSTANTS.LIGHT.TEXT_PRIMARY};
      --n-text-color-2: ${THEME_CONSTANTS.LIGHT.TEXT_SECONDARY};
      --n-text-color-3: rgba(${hexToRgb(THEME_CONSTANTS.LIGHT.TEXT_SECONDARY)}, 0.6);
      --n-primary-color: ${THEME_CONSTANTS.LIGHT.ACCENT_COLOR};
      --n-primary-color-hover: ${colorWithOpacity(THEME_CONSTANTS.LIGHT.ACCENT_COLOR, 0.8)};
      --n-body-color: ${THEME_CONSTANTS.LIGHT.SECONDARY_BG};
      --n-card-color: ${THEME_CONSTANTS.LIGHT.CARD_BG};
      --n-color-modal: ${THEME_CONSTANTS.LIGHT.CARD_BG};
      --n-border-color: ${THEME_CONSTANTS.LIGHT.BORDER_COLOR};
      --n-box-shadow-1: ${THEME_CONSTANTS.LIGHT.CARD_SHADOW};
      --n-box-shadow-2: ${THEME_CONSTANTS.LIGHT.CARD_HOVER_SHADOW};
    }
  `;
}

/**
 * 将CSS变量字符串注入到页面head中
 * @param isDark 是否为深色主题
 * @description 动态创建或更新style标签，注入主题CSS变量
 */
export function injectThemeCSSVariables(isDark: boolean): void {
  // 创建或获取现有的style标签
  let styleElement = document.getElementById(
    "theme-variables",
  ) as HTMLStyleElement;

  if (!styleElement) {
    // 如果不存在，创建新的style标签
    styleElement = document.createElement("style");
    styleElement.id = "theme-variables";
    document.head.appendChild(styleElement);
  }

  // 设置CSS变量内容
  styleElement.textContent = generateThemeCSSVariables(isDark);

  // 设置body类名用于向后兼容
  if (isDark) {
    document.body.classList.remove("theme-light");
    document.body.classList.add("theme-dark");
  } else {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
  }
}

// ============================================================================
// 状态文本样式配置
// ============================================================================

/**
 * 状态文本样式配置
 * 用于股票涨跌状态等文本的样式定义
 */
export const TEXT_STATUS_STYLES = {
  // 上涨状态文本样式
  UP: {
    color: (isDark: boolean) =>
      isDark
        ? THEME_CONSTANTS.DARK.STOCK_UP_COLOR
        : THEME_CONSTANTS.LIGHT.STOCK_UP_COLOR,
    fontWeight: "500" as const,
    fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    // 深色主题下的具体样式
    dark: {
      color: THEME_CONSTANTS.DARK.STOCK_UP_COLOR,
      fontWeight: "500" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
    // 浅色主题下的具体样式
    light: {
      color: THEME_CONSTANTS.LIGHT.STOCK_UP_COLOR,
      fontWeight: "500" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
  },

  // 下跌状态文本样式
  DOWN: {
    color: (isDark: boolean) =>
      isDark
        ? THEME_CONSTANTS.DARK.STOCK_DOWN_COLOR
        : THEME_CONSTANTS.LIGHT.STOCK_DOWN_COLOR,
    fontWeight: "500" as const,
    fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    // 深色主题下的具体样式
    dark: {
      color: THEME_CONSTANTS.DARK.STOCK_DOWN_COLOR,
      fontWeight: "500" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
    // 浅色主题下的具体样式
    light: {
      color: THEME_CONSTANTS.LIGHT.STOCK_DOWN_COLOR,
      fontWeight: "500" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
  },

  // 中性/持平状态文本样式
  NEUTRAL: {
    color: (isDark: boolean) =>
      isDark
        ? THEME_CONSTANTS.DARK.STOCK_FLAT_COLOR
        : THEME_CONSTANTS.LIGHT.STOCK_FLAT_COLOR,
    fontWeight: "400" as const,
    fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    // 深色主题下的具体样式
    dark: {
      color: THEME_CONSTANTS.DARK.STOCK_FLAT_COLOR,
      fontWeight: "400" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
    // 浅色主题下的具体样式
    light: {
      color: THEME_CONSTANTS.LIGHT.STOCK_FLAT_COLOR,
      fontWeight: "400" as const,
      fontSize: THEME_CONSTANTS.DARK.FONT_SIZE_BASE,
    },
  },
} as const;

// ============================================================================
// Flex布局样式配置
// ============================================================================

/**
 * Flex布局样式配置
 * 提供常用的Flex布局模式
 */
export const FLEX_STYLES = {
  // 居中布局 - 水平和垂直都居中
  CENTER: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },

  // 两端对齐布局 - 水平两端对齐，垂直居中
  LAYOUT_BETWEEN: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },

  // 左对齐布局 - 水平左对齐，垂直居中
  LAYOUT_START: {
    display: "flex",
    justifyContent: "flex-start",
    alignItems: "center",
  },

  // 右对齐布局 - 水平右对齐，垂直居中
  LAYOUT_END: {
    display: "flex",
    justifyContent: "flex-end",
    alignItems: "center",
  },

  // 垂直居中布局 - 水平居中，垂直居中
  COLUMN_CENTER: {
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "center",
    alignItems: "center",
  },

  // 垂直两端对齐布局 - 垂直两端对齐，水平居中
  COLUMN_BETWEEN: {
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "space-between",
    alignItems: "center",
  },

  // 垂直填充布局 - 垂直填满，水平居中
  COLUMN_FULL: {
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "space-between",
    alignItems: "stretch",
  },
} as const;

// ============================================================================
// Naive UI 主题配置
// ============================================================================

/**
 * 深色主题配置 - 量化交易专用深色主题
 * 基于主题常量映射到 Naive UI 主题系统
 */
export const darkThemeOverrides: GlobalThemeOverrides = {
  // common 部分用于定义全局通用的主题变量
  common: {
    // ==================== 基础颜色系统 ====================
    primaryColor: THEME_CONSTANTS.DARK.ACCENT_COLOR,
    primaryColorHover: colorWithOpacity(THEME_CONSTANTS.DARK.ACCENT_COLOR, 0.8),
    primaryColorPressed: colorWithOpacity(
      THEME_CONSTANTS.DARK.ACCENT_COLOR,
      0.6,
    ),
    primaryColorSuppl: colorWithOpacity(THEME_CONSTANTS.DARK.ACCENT_COLOR, 0.4),

    // 基础背景色
    bodyColor: THEME_CONSTANTS.DARK.PRIMARY_BG,
    cardColor: THEME_CONSTANTS.DARK.CARD_BG,
    modalColor: THEME_CONSTANTS.DARK.MODAL_BG,
    popoverColor: THEME_CONSTANTS.DARK.POPOVER_BG,
    tableColor: THEME_CONSTANTS.DARK.SECONDARY_BG,
    tableHeaderColor: THEME_CONSTANTS.DARK.CARD_HEADER_BG,

    // 文字颜色系统
    textColorBase: THEME_CONSTANTS.DARK.TEXT_PRIMARY,
    textColor1: THEME_CONSTANTS.DARK.TEXT_PRIMARY,
    textColor2: THEME_CONSTANTS.DARK.TEXT_SECONDARY,
    textColor3: colorWithOpacity(THEME_CONSTANTS.DARK.TEXT_SECONDARY, 0.6),

    // 边框和分割线颜色
    borderColor: THEME_CONSTANTS.DARK.BORDER_COLOR,
    dividerColor: THEME_CONSTANTS.DARK.BORDER_COLOR,

    // 悬停和激活状态背景色
    hoverColor: THEME_CONSTANTS.DARK.HOVER_BG,
    pressedColor: THEME_CONSTANTS.DARK.HOVER_BG,
    clearColor: "rgba(255, 255, 255, 0)",

    // ==================== 圆角和阴影系统 ====================
    borderRadius: THEME_CONSTANTS.DARK.BORDER_RADIUS,
    borderRadiusSmall: THEME_CONSTANTS.DARK.BORDER_RADIUS_SM,

    // 阴影系统
    boxShadow1: THEME_CONSTANTS.DARK.CARD_SHADOW,
    boxShadow2: THEME_CONSTANTS.DARK.CARD_HOVER_SHADOW,
    boxShadow3: "0 0 4px rgba(0, 255, 200, 0.18)",

    // ==================== 字体系统 ====================
    fontFamily: THEME_CONSTANTS.DARK.FONT_FAMILY,
    fontFamilyMono: 'Monaco, "Courier New", monospace',
  },

  // 各组件主题配置（保持原有配置，使用统一常量）
  Button: {
    heightMedium: "26px",
    heightSmall: "22px",
    heightTiny: "19px",
    heightLarge: "29px",
    borderRadiusMedium: THEME_CONSTANTS.DARK.BORDER_RADIUS,
    borderRadiusSmall: THEME_CONSTANTS.DARK.BORDER_RADIUS_SM,
    colorPrimary: THEME_CONSTANTS.DARK.ACCENT_COLOR,
    colorHoverPrimary: colorWithOpacity(THEME_CONSTANTS.DARK.ACCENT_COLOR, 0.8),
    colorPressedPrimary: colorWithOpacity(
      THEME_CONSTANTS.DARK.ACCENT_COLOR,
      0.6,
    ),
    colorFocusPrimary: THEME_CONSTANTS.DARK.ACCENT_COLOR,
    colorDisabledPrimary: colorWithOpacity(
      THEME_CONSTANTS.DARK.ACCENT_COLOR,
      0.3,
    ),
    textColorPrimary: "#FFFFFF",
    textColorHoverPrimary: "#FFFFFF",
    textColorPressedPrimary: "#FFFFFF",
    textColorFocusPrimary: "#FFFFFF",
    textColorDisabledPrimary: "rgba(255, 255, 255, 0.5)",
    borderPrimary: `1px solid ${THEME_CONSTANTS.DARK.ACCENT_COLOR}`,
    borderHoverPrimary: `1px solid ${colorWithOpacity(THEME_CONSTANTS.DARK.ACCENT_COLOR, 0.8)}`,
    borderPressedPrimary: `1px solid ${colorWithOpacity(THEME_CONSTANTS.DARK.ACCENT_COLOR, 0.6)}`,
    borderFocusPrimary: `1px solid ${THEME_CONSTANTS.DARK.ACCENT_COLOR}`,
    colorInfo: THEME_CONSTANTS.DARK.SECONDARY_BG,
    colorHoverInfo: THEME_CONSTANTS.DARK.HOVER_BG,
    colorPressedInfo: THEME_CONSTANTS.DARK.CARD_HEADER_BG,
    borderInfo: `1px solid ${THEME_CONSTANTS.DARK.BORDER_COLOR}`,
    borderHoverInfo: `1px solid ${THEME_CONSTANTS.DARK.ACCENT_COLOR}`,
  },

  // 其他组件配置保持不变，但使用统一常量...
  Menu: {
    fontSize: "12px",
  },
  DataTable: {
    fontSize: "12px",
  },
  Tag: {
    fontSize: "11px",
  },
  Card: {
    color: THEME_CONSTANTS.DARK.CARD_BG,
    colorModal: THEME_CONSTANTS.DARK.CARD_BG,
    borderRadius: THEME_CONSTANTS.DARK.BORDER_RADIUS,
    titleFontSize: "14px",
    fontSize: "12px",
    titleTextColor: THEME_CONSTANTS.DARK.TEXT_PRIMARY,
    textColor: THEME_CONSTANTS.DARK.TEXT_PRIMARY,
    borderColor: THEME_CONSTANTS.DARK.BORDER_COLOR,
    boxShadow: THEME_CONSTANTS.DARK.CARD_SHADOW,
  },

  // 弹出层组件统一背景（Select / Dropdown / DatePicker / Cascader 等复用）
  Popover: {
    color: THEME_CONSTANTS.DARK.POPOVER_BG,
    textColor: THEME_CONSTANTS.DARK.TEXT_PRIMARY,
    dividerColor: THEME_CONSTANTS.DARK.BORDER_COLOR,
  },

  // ... 其他组件配置（DataTable, Input, Select等）保持原样，但确保使用THEME_CONSTANTS
};

/**
 * 浅色主题配置 - 量化交易专用浅色主题
 * 基于主题常量映射到 Naive UI 主题系统
 */
export const lightThemeOverrides: GlobalThemeOverrides = {
  // common 部分用于定义全局通用的主题变量
  common: {
    // ==================== 基础颜色系统 ====================
    primaryColor: THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
    primaryColorHover: colorWithOpacity(
      THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
      0.8,
    ),
    primaryColorPressed: colorWithOpacity(
      THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
      0.6,
    ),
    primaryColorSuppl: colorWithOpacity(
      THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
      0.4,
    ),

    // 基础背景色
    bodyColor: THEME_CONSTANTS.LIGHT.SECONDARY_BG,
    cardColor: THEME_CONSTANTS.LIGHT.CARD_BG,
    modalColor: THEME_CONSTANTS.LIGHT.CARD_BG,
    popoverColor: THEME_CONSTANTS.LIGHT.CARD_BG,
    tableColor: THEME_CONSTANTS.LIGHT.CARD_BG,
    tableHeaderColor: THEME_CONSTANTS.LIGHT.CARD_HEADER_BG,

    // 文字颜色系统
    textColorBase: THEME_CONSTANTS.LIGHT.TEXT_PRIMARY,
    textColor1: THEME_CONSTANTS.LIGHT.TEXT_PRIMARY,
    textColor2: THEME_CONSTANTS.LIGHT.TEXT_SECONDARY,
    textColor3: colorWithOpacity(THEME_CONSTANTS.LIGHT.TEXT_SECONDARY, 0.6),

    // 边框和分割线颜色
    borderColor: THEME_CONSTANTS.LIGHT.BORDER_COLOR,
    dividerColor: THEME_CONSTANTS.LIGHT.BORDER_COLOR,

    // 悬停和激活状态背景色
    hoverColor: THEME_CONSTANTS.LIGHT.HOVER_BG,
    pressedColor: THEME_CONSTANTS.LIGHT.BORDER_COLOR,
    clearColor: "rgba(255, 255, 255, 0)",

    // ==================== 圆角和阴影系统 ====================
    borderRadius: THEME_CONSTANTS.LIGHT.BORDER_RADIUS,
    borderRadiusSmall: THEME_CONSTANTS.LIGHT.BORDER_RADIUS_SM,

    // 阴影系统
    boxShadow1: THEME_CONSTANTS.LIGHT.CARD_SHADOW,
    boxShadow2: THEME_CONSTANTS.LIGHT.CARD_HOVER_SHADOW,
    boxShadow3: "0 16px 48px rgba(0, 0, 0, 0.16)",

    // ==================== 字体系统 ====================
    fontFamily: THEME_CONSTANTS.LIGHT.FONT_FAMILY,
    fontFamilyMono: 'Monaco, "Courier New", monospace',
  },

  // 各组件主题配置（保持原有配置，使用统一常量）
  Button: {
    heightMedium: "26px",
    heightSmall: "22px",
    heightTiny: "19px",
    heightLarge: "29px",
    borderRadiusMedium: THEME_CONSTANTS.LIGHT.BORDER_RADIUS,
    borderRadiusSmall: THEME_CONSTANTS.LIGHT.BORDER_RADIUS_SM,
    colorPrimary: THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
    colorHoverPrimary: colorWithOpacity(
      THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
      0.8,
    ),
    colorPressedPrimary: colorWithOpacity(
      THEME_CONSTANTS.LIGHT.ACCENT_COLOR,
      0.6,
    ),
    colorInfo: THEME_CONSTANTS.LIGHT.TOOLBAR_BG,
    colorHoverInfo: THEME_CONSTANTS.LIGHT.HOVER_BG,
    colorPressedInfo: THEME_CONSTANTS.LIGHT.BORDER_COLOR,
    borderInfo: `1px solid ${THEME_CONSTANTS.LIGHT.BORDER_COLOR}`,
    borderHoverInfo: `1px solid ${THEME_CONSTANTS.LIGHT.ACCENT_COLOR}`,
  },

  Card: {
    color: THEME_CONSTANTS.LIGHT.CARD_BG,
    borderRadius: THEME_CONSTANTS.LIGHT.BORDER_RADIUS,
    titleFontSize: "14px",
    fontSize: "12px",
    titleTextColor: THEME_CONSTANTS.LIGHT.TEXT_PRIMARY,
    textColor: THEME_CONSTANTS.LIGHT.TEXT_PRIMARY,
    borderColor: THEME_CONSTANTS.LIGHT.BORDER_COLOR,
    boxShadow: THEME_CONSTANTS.LIGHT.CARD_SHADOW,
  },

  Menu: {
    fontSize: "12px",
  },
  DataTable: {
    fontSize: "12px",
  },
  Tag: {
    fontSize: "11px",
  },
  // ... 其他组件配置（Card, DataTable, Input, Message等）保持原样，但确保使用THEME_CONSTANTS
};

// ============================================================================
// 工具函数
// ============================================================================

/**
 * 获取当前主题配置
 * @param isDark 是否为深色主题
 * @returns 对应的Naive UI主题配置
 */
export function getThemeOverrides(isDark: boolean): GlobalThemeOverrides {
  return isDark ? darkThemeOverrides : lightThemeOverrides;
}

/**
 * 获取状态文本样式
 * @param status 状态类型：'UP' | 'DOWN' | 'NEUTRAL'
 * @param isDark 是否为深色主题
 * @returns 对应的文本样式对象
 */
export function getTextStatusStyle(
  status: "UP" | "DOWN" | "NEUTRAL",
  isDark: boolean,
) {
  const style = TEXT_STATUS_STYLES[status];
  return isDark ? style.dark : style.light;
}

/**
 * 获取Flex布局样式
 * @param type 布局类型：'CENTER' | 'LAYOUT_BETWEEN' | 'LAYOUT_START' | 'LAYOUT_END' | 'COLUMN_CENTER' | 'COLUMN_BETWEEN' | 'COLUMN_FULL'
 * @returns 对应的Flex样式对象
 */
export function getFlexStyle(type: keyof typeof FLEX_STYLES) {
  return FLEX_STYLES[type];
}

/**
 * 获取当前主题的CSS变量字符串（不注入，仅返回）
 * @param isDark 是否为深色主题
 * @returns CSS变量字符串
 */
export function getThemeCSSVariables(isDark: boolean): string {
  return generateThemeCSSVariables(isDark);
}

/**
 * 初始化主题 - 应用启动时调用
 * @param isDark 初始主题是否为深色
 * @description 在应用启动时调用，注入初始主题CSS变量
 */
export function initTheme(isDark: boolean = true): void {
  injectThemeCSSVariables(isDark);
}

// ============================================================================
// P0: 图表色板 — 直接取用，供 ECharts 按需注册
// ============================================================================

/** 获取当前主题图表 8 色色板 */
export function getChartPalette(
  isDark: boolean = true,
): readonly string[] {
  return isDark
    ? THEME_CONSTANTS.DARK.CHART_PALETTE
    : THEME_CONSTANTS.LIGHT.CHART_PALETTE;
}

// ============================================================================
// P3: 涨跌配色方案 — 根据用户偏好返回
// ============================================================================

export type StockScheme = "INTERNATIONAL" | "ASHARE";

/** 获取当前涨跌配色 */
export function getStockColors(
  scheme: StockScheme = "ASHARE",
): { up: string; down: string; flat: string } {
  return isDarkTheme()
    ? THEME_CONSTANTS.DARK.STOCK_SCHEMES[scheme]
    : THEME_CONSTANTS.LIGHT.STOCK_SCHEMES[scheme];
}

// ============================================================================
// P4: 渐变 — 按名称取渐变字符串
// ============================================================================

/** 获取霓虹渐变 CSS 值 */
export function getGradient(
  name: keyof typeof THEME_CONSTANTS.DARK.GRADIENTS,
): string {
  const theme = isDarkTheme() ? THEME_CONSTANTS.DARK : THEME_CONSTANTS.LIGHT;
  return theme.GRADIENTS[name];
}

// ============================================================================
// 内部工具
// ============================================================================

let _isDarkCache = true;

/** 记录当前主题（由 App.vue / main.ts 调用时更新） */
export function setCurrentThemeMode(isDark: boolean): void {
  _isDarkCache = isDark;
}

function isDarkTheme(): boolean {
  return _isDarkCache;
}

// ============================================================================
// 类型和常量导出
// ============================================================================

export type { GlobalThemeOverrides };
export { THEME_CONSTANTS };
