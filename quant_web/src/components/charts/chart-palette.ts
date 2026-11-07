// chart-palette.ts — canvas 绘图专用色板（集中常量）
//
// ⚠️ 为什么不能用 design-tokens.ts：
//    canvas 绘图原语（lightweight-charts primitives）无法解析 CSS 变量，而
//    design-tokens.ts 的颜色全部是 "var(--color-*, #hex)" 形态，直接传给 canvas
//    会被当作非法颜色静默失效。
//    → 绘图色必须在**此处**以 hex 常量集中定义，禁止在各页面再次散落硬编码。
//
// ⚠️ 涨跌色沿用 K 线容器既有取值（LightweightKLine.vue 蜡烛 upColor/downColor），
//    以保证同一画布内颜色一致。页面上另一套 (#ef5350/#26a69a) 属存量散落，本包不动。

/** 涨跌（A 股惯例：红涨绿跌）—— 与 K 线蜡烛一致 */
export const CHART_COLORS = {
  up: "#e83939",
  down: "#1dbd60",
} as const;

/** 绘图工具配色（4 类工具各自可辨识，且不与红/绿蜡烛冲突） */
export const DRAW_COLORS = {
  trendLine: "#FF9800",
  horizontalLine: "#448AFF",
  verticalLine: "#AB47BC",
  annotationLabel: "#FFD54F",
  annotationBg: "rgba(20, 26, 44, 0.85)",
  /** 选中高亮 */
  selected: "#00E5FF",
} as const;

/** 绘图默认线宽 / 线型（0 = 实线） */
export const DRAW_DEFAULTS = {
  lineWidth: 2,
  selectedLineWidth: 3,
  lineStyle: 0 as const,
} as const;

/**
 * 均线（MA）配色 —— **对齐同花顺默认口径**（白 / 黄 / 紫 / 绿 / 蓝）。
 *
 * ⚠️ 2026-10-11 修复：此前颜色硬编码在 `LightweightKLine.vue` 内且**无任何图例/标注**，
 *    用户看不出橙/蓝/紫分别是什么（实为 MA5/MA10/MA20）。现集中到此处并配图例。
 * ⚠️ 同花顺的均线色可自定义 → 若与本机不符，改这里的值即可（单一事实源）。
 */
export const MA_COLORS: Record<number, string> = {
  5: "#FFFFFF", // 白
  10: "#FFD700", // 黄
  20: "#E040FB", // 紫
  30: "#00E676", // 绿
  60: "#448AFF", // 蓝
};

/** 未在 `MA_COLORS` 中声明的周期（自定义 maLines）按序回退 */
export const MA_FALLBACK_COLORS = [
  "#FFD54F",
  "#4DD0E1",
  "#FF8A65",
  "#AED581",
] as const;
