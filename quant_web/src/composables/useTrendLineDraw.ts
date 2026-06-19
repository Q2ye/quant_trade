// useTrendLineDraw.ts — 交互式趋势线绘制状态机
// 监听图表容器的 DOM 鼠标事件，在 lightweight-charts 图表上绘制趋势线
// 使用 coordinateToTime / coordinateToPrice 将像素坐标转回时间/价格
import { ref, type Ref } from "vue";
import {
  type IChartApi,
  type ISeriesApi,
  type Time,
  type SeriesType,
} from "lightweight-charts";
import type { TrendLineData } from "@/components/charts/primitives/types";

/** 绘制状态 */
export type DrawState = "idle" | "drawing" | "preview";

/** 趋势线绘制事件 */
export interface TrendLineDrawEvent {
  data: TrendLineData;
}

/** 趋势线绘制配置 */
export interface TrendLineDrawOptions {
  /** 默认颜色 */
  color?: string;
  /** 默认线宽 */
  lineWidth?: number;
  /** 默认线型 */
  lineStyle?: 0 | 1 | 2 | 3 | 4;
  /** 是否默认延长右侧 */
  extendRight?: boolean;
}

export function useTrendLineDraw(options: TrendLineDrawOptions = {}) {
  const state: Ref<DrawState> = ref("idle");
  const previewData: Ref<TrendLineData | null> = ref(null);

  const {
    color = "#FF9800",
    lineWidth = 2,
    lineStyle = 0,
    extendRight = true,
  } = options;

  // 当前正在绘制中的临时数据
  let _startTime: Time | null = null;
  let _startPrice: number | null = null;
  let _chart: IChartApi | null = null;
  let _series: ISeriesApi<SeriesType, Time> | null = null;
  let _container: HTMLElement | null = null;
  let _idCounter = 0;

  // DOM 事件处理器引用（用于移除监听）
  let _onMouseMove: ((e: MouseEvent) => void) | null = null;
  let _onMouseUp: ((e: MouseEvent) => void) | null = null;
  let _onKeyDown: ((e: KeyboardEvent) => void) | null = null;

  /** 将鼠标事件坐标转换为 (time, price) */
  function mouseToTimePrice(e: MouseEvent): { time: Time | null; price: number | null } {
    if (!_chart || !_container || !_series) return { time: null, price: null };

    const rect = _container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const time = _chart.timeScale().coordinateToTime(x);
    const price = _series.coordinateToPrice(y);

    return {
      time: time ?? null,
      price: price !== null ? (typeof price === "number" ? price : Number(price)) : null,
    };
  }

  /** 开始绘制 */
  function activate(
    chart: IChartApi,
    series: ISeriesApi<SeriesType, Time>,
    container: HTMLElement,
  ): void {
    if (state.value !== "idle") return;

    _chart = chart;
    _series = series;
    _container = container;

    state.value = "drawing";

    // 修改容器光标样式
    container.style.cursor = "crosshair";

    // mousedown: 记录起点
    const onMouseDown = (e: MouseEvent) => {
      if (state.value !== "drawing") return;
      // 只响应左键
      if (e.button !== 0) return;

      const { time, price } = mouseToTimePrice(e);
      if (time === null || price === null) return;

      _startTime = time;
      _startPrice = price;

      // 初始化预览数据
      previewData.value = {
        id: `drawing-${Date.now()}-${++_idCounter}`,
        type: "trendLine",
        startTime: time,
        endTime: time, // 起点=终点（初始）
        startPrice: price,
        endPrice: price,
        lineColor: color,
        lineWidth,
        lineStyle,
        extendLeft: false,
        extendRight,
      };

      state.value = "preview";

      // 绑定 move/up 事件
      _onMouseMove = onMouseMoveHandler;
      _onMouseUp = onMouseUpHandler;
      window.addEventListener("mousemove", _onMouseMove);
      window.addEventListener("mouseup", _onMouseUp);
    };

    // mousemove: 更新终点
    const onMouseMoveHandler = (e: MouseEvent) => {
      if (state.value !== "preview" || !previewData.value) return;

      const { time, price } = mouseToTimePrice(e);
      if (time === null || price === null) return;

      previewData.value = {
        ...previewData.value,
        endTime: time,
        endPrice: price,
      };
    };

    // mouseup: 完成绘制
    const onMouseUpHandler = (e: MouseEvent) => {
      window.removeEventListener("mousemove", _onMouseMove!);
      window.removeEventListener("mouseup", _onMouseUp!);
      _onMouseMove = null;
      _onMouseUp = null;

      if (state.value !== "preview" || !previewData.value || !_startTime || _startPrice === null) {
        resetInternal();
        return;
      }

      const { time, price } = mouseToTimePrice(e);
      if (time === null || price === null) {
        // 鼠标释放点无效，取消绘制
        previewData.value = null;
        resetInternal();
        return;
      }

      // 如果起点和终点太近（< 2 个像素），视为误触，取消
      const x1 = _chart?.timeScale().timeToCoordinate(_startTime);
      const x2 = _chart?.timeScale().timeToCoordinate(time);
      if (x1 !== null && x2 !== null && x1 !== undefined && x2 !== undefined) {
        const dx = (x2 as number) - (x1 as number);
        if (Math.abs(dx) < 5) {
          previewData.value = null;
          resetInternal();
          return;
        }
      }

      // 最终确定趋势线
      previewData.value = {
        ...previewData.value,
        endTime: time,
        endPrice: price,
      };

      // 保持 preview 数据供父组件消费
      // 父组件应在收到数据后调用 deactivate()
    };

    // Escape 键取消
    _onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        cancel();
      }
    };
    window.addEventListener("keydown", _onKeyDown);

    container.addEventListener("mousedown", onMouseDown);
    // 存储引用以便 deactivate 时移除
    (_container as any).__trendLineDrawHandler = onMouseDown;
  }

  /** 停止绘制并清理 */
  function deactivate(): void {
    resetInternal();
    state.value = "idle";
  }

  /** 取消当前绘制 */
  function cancel(): void {
    previewData.value = null;
    resetInternal();
    state.value = "drawing"; // 回到 drawing 状态等待下一次 mousedown
  }

  /** 完成当前趋势线并消费预览数据 */
  function consumePreview(): TrendLineData | null {
    const data = previewData.value;
    previewData.value = null;
    deactivate();
    return data;
  }

  /** 内部重置 */
  function resetInternal(): void {
    if (_container && (_container as any).__trendLineDrawHandler) {
      _container.removeEventListener("mousedown", (_container as any).__trendLineDrawHandler);
      delete (_container as any).__trendLineDrawHandler;
    }
    if (_onMouseMove) {
      window.removeEventListener("mousemove", _onMouseMove);
      _onMouseMove = null;
    }
    if (_onMouseUp) {
      window.removeEventListener("mouseup", _onMouseUp);
      _onMouseUp = null;
    }
    if (_onKeyDown) {
      window.removeEventListener("keydown", _onKeyDown);
      _onKeyDown = null;
    }
    if (_container) {
      _container.style.cursor = "";
    }
    _startTime = null;
    _startPrice = null;
  }

  /** 完全清理（组件卸载时调用） */
  function dispose(): void {
    cancel();
    deactivate();
    _chart = null;
    _series = null;
    _container = null;
  }

  return {
    state,
    previewData,
    activate,
    deactivate,
    cancel,
    consumePreview,
    dispose,
  };
}
