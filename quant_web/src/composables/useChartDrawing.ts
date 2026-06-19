// useChartDrawing.ts — 图表绘制工具入口
// 组合 useTrendLineDraw + usePrimitiveManager，提供完整的绘制交互体验
// 在组件中只需调用 activate(chart, series, container) 即可启用趋势线绘制
import { ref, watch, type Ref } from "vue";
import {
  type IChartApi,
  type ISeriesApi,
  type ISeriesPrimitive,
  type Time,
  type SeriesType,
} from "lightweight-charts";
import { TrendLinePrimitive } from "@/components/charts/primitives/TrendLine";
import { useTrendLineDraw } from "./useTrendLineDraw";
import { usePrimitiveManager } from "./usePrimitiveManager";
import type { TrendLineData } from "@/components/charts/primitives/types";

export interface ChartDrawingOptions {
  /** 趋势线默认颜色 */
  trendColor?: string;
  /** 趋势线默认线宽 */
  trendWidth?: number;
  /** 是否默认延长右侧（射线） */
  extendRight?: boolean;
}

export function useChartDrawing(opts: ChartDrawingOptions = {}) {
  const trendDraw = useTrendLineDraw({
    color: opts.trendColor ?? "#FF9800",
    lineWidth: opts.trendWidth ?? 2,
    extendRight: opts.extendRight ?? true,
  });

  const primitiveManager = usePrimitiveManager();

  /** 已确认的趋势线数据列表（持久化用） */
  const confirmedDrawings: Ref<TrendLineData[]> = ref([]);

  // 预览原语实例（临时绘制中的趋势线）
  let _previewPrimitive: TrendLinePrimitive | null = null;

  /** 监视预览数据变化，实时更新预览原语 */
  watch(
    () => trendDraw.previewData.value,
    (data) => {
      // 移除旧预览
      if (_previewPrimitive) {
        primitiveManager.detach("__preview__");
        _previewPrimitive = null;
      }

      if (data) {
        _previewPrimitive = new TrendLinePrimitive(data);
        primitiveManager.attach("__preview__", _previewPrimitive);
      }
    },
  );

  /** 激活绘制模式 */
  function activate(
    chart: IChartApi,
    series: ISeriesApi<SeriesType, Time>,
    container: HTMLElement,
  ): void {
    primitiveManager.bind(series, () => {
      // 请求重绘回调
    });
    trendDraw.activate(chart, series, container);
  }

  /** 停止绘制模式 */
  function deactivate(): void {
    trendDraw.deactivate();
    if (_previewPrimitive) {
      primitiveManager.detach("__preview__");
      _previewPrimitive = null;
    }
  }

  /** 确认当前绘制的趋势线并存入列表 */
  function confirmDrawing(): TrendLineData | null {
    const data = trendDraw.consumePreview();
    if (data) {
      confirmedDrawings.value = [...confirmedDrawings.value, data];
      // 附加为持久原语
      const prim = new TrendLinePrimitive(data);
      primitiveManager.attach(data.id, prim);
    }
    return data;
  }

  /** 取消当前绘制 */
  function cancelDrawing(): void {
    trendDraw.cancel();
    if (_previewPrimitive) {
      primitiveManager.detach("__preview__");
      _previewPrimitive = null;
    }
  }

  /** 删除指定趋势线 */
  function removeDrawing(id: string): void {
    confirmedDrawings.value = confirmedDrawings.value.filter((d) => d.id !== id);
    primitiveManager.detach(id);
  }

  /** 清空所有趋势线 */
  function clearAll(): void {
    confirmedDrawings.value = [];
    primitiveManager.detachAll();
    if (_previewPrimitive) {
      _previewPrimitive = null;
    }
  }

  /** 从已存储数据恢复趋势线（页面加载时） */
  function restoreDrawings(drawings: TrendLineData[], chart: IChartApi, series: ISeriesApi<SeriesType, Time>): void {
    primitiveManager.bind(series, () => {});
    confirmedDrawings.value = [...drawings];
    for (const d of drawings) {
      const prim = new TrendLinePrimitive(d);
      primitiveManager.attach(d.id, prim);
    }
  }

  /** 完全清理 */
  function dispose(): void {
    trendDraw.dispose();
    primitiveManager.dispose();
    confirmedDrawings.value = [];
    _previewPrimitive = null;
  }

  return {
    /** 绘制状态机 */
    drawState: trendDraw.state,
    /** 预览数据 */
    previewData: trendDraw.previewData,
    /** 已确认的趋势线列表 */
    confirmedDrawings,
    /** 激活绘制模式 */
    activate,
    /** 停止绘制模式 */
    deactivate,
    /** 确认当前绘制 */
    confirmDrawing,
    /** 取消当前绘制 */
    cancelDrawing,
    /** 删除趋势线 */
    removeDrawing,
    /** 清空全部 */
    clearAll,
    /** 从持久化数据恢复 */
    restoreDrawings,
    /** 获取原语管理器 */
    getPrimitiveManager: () => primitiveManager,
    /** 完全清理 */
    dispose,
  };
}
