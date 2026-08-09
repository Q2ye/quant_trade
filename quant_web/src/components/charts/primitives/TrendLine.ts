// TrendLine.ts — 趋势线原语
// 存储起止时间戳 + 价格，每次 draw() 动态通过 timeToCoordinate 重算坐标
import {
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type PriceToCoordinateConverter,
} from "lightweight-charts";
import type { TrendLineData, LineStyle } from "./types";

function lineStyleToDash(style: LineStyle): number[] {
  switch (style) {
    case 0: return [];
    case 1: return [6, 3];
    case 2: return [2, 2];
    case 3: return [8, 3, 2, 3];
    case 4: return [8, 3, 2, 3, 2, 3];
    default: return [];
  }
}

export class TrendLinePrimitive implements ISeriesPrimitive<Time> {
  _chart: import("lightweight-charts").IChartApi | null = null;
  _series: import("lightweight-charts").ISeriesApi<"Line", Time> | null = null;
  _data: TrendLineData;
  private _requestUpdate: (() => void) | null = null;

  constructor(data: TrendLineData) {
    this._data = { ...data };
  }

  attached(params: SeriesAttachedParameter<Time>): void {
    this._chart = params.chart;
    // @ts-expect-error series 在 attached 参数中提供（v5.2）
    this._series = params.series as any;
    this._requestUpdate = params.requestUpdate;
  }

  detached(): void {
    this._chart = null;
    this._series = null;
    this._requestUpdate = null;
  }

  updateAllViews(): void {
    this._requestUpdate?.();
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  paneViews(): any {
    const self = this;
    return [{
      zOrder: () => "top" as const,
      renderer: () => ({
        draw(
          target: any,
          _utils?: unknown,
        ): void {
          const chart = self._chart;
          const series = self._series;
          const data = self._data;
          if (!chart || !series) return;

          const timeScale = chart.timeScale();
          const chartWidth = timeScale.width();

          const x1 = timeScale.timeToCoordinate(data.startTime);
          const y1 = series.priceToCoordinate(data.startPrice);
          const x2 = timeScale.timeToCoordinate(data.endTime);
          const y2 = series.priceToCoordinate(data.endPrice);

          if (x1 === null || y1 === null || x2 === null || y2 === null) return;

          let dx1 = x1 as number; let dy1 = y1 as number;
          let dx2 = x2 as number; let dy2 = y2 as number;

          if (data.extendLeft || data.extendRight) {
            const slopeX = dx2 - dx1;
            const slopeY = dy2 - dy1;
            if (Math.abs(slopeX) > 0.001) {
              const slope = slopeY / slopeX;
              if (data.extendLeft) { dx1 = 0; dy1 = dy1 - slope * (x1 as number); }
              if (data.extendRight) { dx2 = chartWidth; dy2 = dy2 + slope * (chartWidth - (x2 as number)); }
            }
          }

          if ((dx1 < -100 && dx2 < -100) || (dx1 > chartWidth + 100 && dx2 > chartWidth + 100)) return;

          target.useBitmapCoordinateSpace((scope: { context: CanvasRenderingContext2D }) => {
            const ctx = scope.context;
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(dx1, dy1);
            ctx.lineTo(dx2, dy2);
            ctx.strokeStyle = data.lineColor;
            ctx.lineWidth = data.lineWidth;
            const dash = lineStyleToDash(data.lineStyle);
            if (dash.length > 0) ctx.setLineDash(dash);
            ctx.stroke();
            ctx.restore();
          });
        },
      }),
    }];
  }

  updateData(partial: Partial<TrendLineData>): void {
    Object.assign(this._data, partial);
    this._requestUpdate?.();
  }

  getData(): Readonly<TrendLineData> {
    return this._data;
  }
}
