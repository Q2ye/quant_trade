// useTimeCoordinate.ts — lightweight-charts 坐标转换封装 + 脏检查
// 核心约束：所有绘制元素只存储时间戳，每次渲染动态通过 timeToCoordinate 计算坐标
import { type IChartApi, type ISeriesApi, type Time, type SeriesType } from "lightweight-charts";

/** 坐标转换结果 */
export interface CoordResult {
  x: number;
  y: number;
}

/** 时间范围（用于脏检查） */
export interface TimeRangeCache {
  from: number; // epoch seconds
  to: number;
  chartWidth: number;
}

export function useTimeCoordinate() {
  let _lastRange: TimeRangeCache | null = null;
  let _dirty = true;

  /** 标记为脏——下次 needsRecalc 返回 true */
  function markDirty(): void {
    _dirty = true;
  }

  /**
   * 检查是否需要重新计算坐标
   * @returns true = 视口已变化，需要重新调用 timeToCoordinate
   */
  function needsRecalc(visibleRange: { from: Time; to: Time } | null, chartWidth: number): boolean {
    if (_dirty) return true;
    if (!visibleRange) return true;
    if (!_lastRange) return true;

    const fromSec = toEpochSeconds(visibleRange.from);
    const toSec = toEpochSeconds(visibleRange.to);

    if (fromSec !== _lastRange.from) return true;
    if (toSec !== _lastRange.to) return true;
    if (chartWidth !== _lastRange.chartWidth) return true;

    return false;
  }

  /** 更新缓存——在一次 render 完成后调用 */
  function updateCache(visibleRange: { from: Time; to: Time } | null, chartWidth: number): void {
    if (!visibleRange) return;
    _lastRange = {
      from: toEpochSeconds(visibleRange.from),
      to: toEpochSeconds(visibleRange.to),
      chartWidth,
    };
    _dirty = false;
  }

  /** 将 Time 转为 epoch 秒 */
  function toEpochSeconds(t: Time): number {
    if (typeof t === "number") return t as number;
    if (typeof t === "string") {
      // 'YYYY-MM-DD' → 解析为 UTC 午夜
      return Math.floor(new Date(t + "T00:00:00Z").getTime() / 1000);
    }
    // BusinessDay/UTCTimestamp 等其他类型
    return Math.floor(new Date(String(t)).getTime() / 1000);
  }

  /**
   * 将时间戳 + 价格转为图表画布坐标
   * @param chart - 图表实例
   * @param series - 系列实例（用于 price → Y 坐标）
   * @param time - 时间戳
   * @param price - 价格
   * @returns { x, y } 或 null（时间或价格超出范围）
   */
  function toCoord(
    chart: IChartApi | null,
    series: ISeriesApi<SeriesType, Time> | null,
    time: Time,
    price: number,
  ): CoordResult | null {
    if (!chart || !series) return null;

    const x = chart.timeScale().timeToCoordinate(time);
    if (x === null) return null;

    const y = series.priceToCoordinate(price);
    if (y === null) return null;

    return { x, y };
  }

  /**
   * 仅转换时间为 X 坐标（不关心价格）
   */
  function timeToX(chart: IChartApi | null, time: Time): number | null {
    if (!chart) return null;
    return chart.timeScale().timeToCoordinate(time);
  }

  /**
   * 将 X 坐标转回时间
   */
  function xToTime(chart: IChartApi | null, x: number): Time | null {
    if (!chart) return null;
    return chart.timeScale().coordinateToTime(x);
  }

  /**
   * 将 Y 坐标转回价格
   */
  function yToPrice(series: ISeriesApi<SeriesType, Time> | null, y: number): number | null {
    if (!series) return null;
    const p = series.coordinateToPrice(y);
    if (p === null) return null;
    // coordinateToPrice 返回 BarPrice（可能是 number）
    return typeof p === "number" ? p : Number(p);
  }

  /** 清除所有缓存 */
  function reset(): void {
    _lastRange = null;
    _dirty = true;
  }

  return {
    markDirty,
    needsRecalc,
    updateCache,
    toCoord,
    timeToX,
    xToTime,
    yToPrice,
    toEpochSeconds,
    reset,
  };
}
