// useChartLifecycle.ts — lightweight-charts 图表生命周期管理
// 从 EquityCurveChart / DrawdownAreaChart / LightweightKLine 提取公共逻辑
import { ref, onBeforeUnmount, type Ref } from "vue";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type DeepPartial,
  type ChartOptions,
  type Time,
} from "lightweight-charts";

export interface ChartLifecycleOptions {
  /** 容器高度（px） */
  height?: number;
  /** 容器宽度（px），默认取容器 clientWidth */
  width?: number;
  /** 布局覆盖（transparent 背景等固定配置会被合并） */
  layout?: DeepPartial<ChartOptions["layout"]>;
  /** 时间轴选项覆盖 */
  timeScale?: DeepPartial<ChartOptions["timeScale"]>;
  /** 右键价格轴选项覆盖 */
  rightPriceScale?: DeepPartial<ChartOptions["rightPriceScale"]>;
  /** 网格选项覆盖 */
  grid?: DeepPartial<ChartOptions["grid"]>;
  /** 是否显示归因 logo（默认 false） */
  attributionLogo?: boolean;
}

const DARK_TEXT = "#a0a0a0";
const LIGHT_TEXT = "#666666";
const DARK_BORDER = "rgba(255,255,255,0.08)";
const LIGHT_BORDER = "rgba(0,0,0,0.08)";
const DARK_GRID = "rgba(255,255,255,0.04)";
const LIGHT_GRID = "rgba(0,0,0,0.04)";

/** 检测当前是否深色模式（基于 CSS 变量 --body-color） */
export function isDarkMode(): boolean {
  if (typeof document === "undefined") return true;
  const el = document.documentElement;
  const bg =
    getComputedStyle(el).getPropertyValue("--body-color") ||
    getComputedStyle(el).getPropertyValue("--color-bg-body");
  if (bg) {
    const rgb = bg.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      return (Number(rgb[0]) + Number(rgb[1]) + Number(rgb[2])) / 3 < 128;
    }
  }
  return true;
}

export function useChartLifecycle(options: ChartLifecycleOptions = {}) {
  const chartContainer = ref<HTMLDivElement>() as Ref<HTMLDivElement | undefined>;
  let chart: IChartApi | null = null;

  // ------- 创建 -------
  function createChartInstance(): IChartApi | null {
    const el = chartContainer.value;
    if (!el) return null;
    const w = options.width ?? el.clientWidth;
    const h = options.height ?? 420;
    if (!w || w <= 0) return null;

    if (chart) destroyChart();

    const dark = isDarkMode();
    chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? DARK_TEXT : LIGHT_TEXT,
        attributionLogo: options.attributionLogo ?? false,
        ...options.layout,
      },
      grid: {
        vertLines: { color: dark ? DARK_GRID : LIGHT_GRID },
        horzLines: { color: dark ? DARK_GRID : LIGHT_GRID },
        ...options.grid,
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: dark ? DARK_BORDER : LIGHT_BORDER,
        ...options.rightPriceScale,
      },
      timeScale: {
        borderColor: dark ? DARK_BORDER : LIGHT_BORDER,
        timeVisible: true,
        ...options.timeScale,
      },
      handleScroll: { vertTouchDrag: false },
      width: w,
      height: h,
    } as DeepPartial<ChartOptions> as ChartOptions);

    return chart;
  }

  // ------- 销毁 -------
  function destroyChart(): void {
    if (chart) {
      chart.remove();
      chart = null;
    }
  }

  // ------- resize (ResizeObserver — 业界标准方案) -------
  let _resizeObserver: ResizeObserver | null = null;

  function handleResize(): void {
    if (!chart || !chartContainer.value) return;
    const newW = options.width ?? chartContainer.value.clientWidth;
    const newH = options.height ?? 420;
    if (newW <= 0) return;
    // ⚠️ 使用 chart.resize() 而非 applyOptions({ width })
    // lightweight-charts 的 applyOptions 不会真正重绘 canvas 尺寸
    chart.resize(newW, newH);
  }

  // ------- 主题切换 -------
  function handleThemeChange(): void {
    if (!chart) return;
    const dark = isDarkMode();
    chart.applyOptions({
      layout: { textColor: dark ? DARK_TEXT : LIGHT_TEXT },
      grid: {
        vertLines: { color: dark ? DARK_GRID : LIGHT_GRID },
        horzLines: { color: dark ? DARK_GRID : LIGHT_GRID },
      },
      rightPriceScale: {
        borderColor: dark ? DARK_BORDER : LIGHT_BORDER,
      },
      timeScale: {
        borderColor: dark ? DARK_BORDER : LIGHT_BORDER,
      },
    } as DeepPartial<ChartOptions>);
  }

  // ------- 注册全局事件 (ResizeObserver 替代 window.resize) -------
  function bindGlobalEvents(): void {
    window.addEventListener("theme-change", handleThemeChange);
    if (chartContainer.value) {
      _resizeObserver = new ResizeObserver(() => handleResize());
      _resizeObserver.observe(chartContainer.value);
      // 立即同步一次，防止 chart 创建时容器尚未完成布局
      handleResize();
    }
  }

  function unbindGlobalEvents(): void {
    window.removeEventListener("theme-change", handleThemeChange);
    if (_resizeObserver) {
      _resizeObserver.disconnect();
      _resizeObserver = null;
    }
  }

  // ------- 获取实例 -------
  function getChart(): IChartApi | null {
    return chart;
  }

  // ------- fitContent 快捷方法 -------
  function fitContent(): void {
    chart?.timeScale().fitContent();
  }

  // 清理
  onBeforeUnmount(() => {
    unbindGlobalEvents();
    destroyChart();
  });

  return {
    chartContainer,
    createChartInstance,
    destroyChart,
    handleResize,
    handleThemeChange,
    bindGlobalEvents,
    unbindGlobalEvents,
    getChart,
    fitContent,
    isDarkMode,
  };
}
