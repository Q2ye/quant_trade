// VerticalLine.ts — 垂直线原语（事件标记、交易日分隔）
import {
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type PriceToCoordinateConverter,
} from "lightweight-charts";
import type { VerticalLineData, LineStyle } from "./types";

function lineStyleToDash(style: LineStyle): number[] {
  switch (style) {
    case 0: return []; case 1: return [6, 3]; case 2: return [2, 2];
    case 3: return [8, 3, 2, 3]; case 4: return [8, 3, 2, 3, 2, 3]; default: return [];
  }
}

export class VerticalLinePrimitive implements ISeriesPrimitive<Time> {
  _chart: import("lightweight-charts").IChartApi | null = null;
  _series: import("lightweight-charts").ISeriesApi<"Line", Time> | null = null;
  _data: VerticalLineData;
  private _requestUpdate: (() => void) | null = null;

  constructor(data: VerticalLineData) { this._data = { ...data }; }

  attached(params: SeriesAttachedParameter<Time>): void {
    this._chart = params.chart;
    // @ts-expect-error series 在 attached 参数中提供（v5.2）
    this._series = params.series as any;
    this._requestUpdate = params.requestUpdate;
  }

  detached(): void { this._chart = null; this._series = null; this._requestUpdate = null; }
  updateAllViews(): void { this._requestUpdate?.(); }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  paneViews(): any {
    const self = this;
    return [{
      zOrder: () => "normal" as const,
      renderer: () => ({
        draw(target: any, _utils?: unknown): void {
          const chart = self._chart;
          const series = self._series;
          const data = self._data;
          if (!chart || !series) return;
          const ts = chart.timeScale();
          const x = ts.timeToCoordinate(data.time);
          if (x === null) return;
          const cw = ts.width();
          if ((x as number) < 0 || (x as number) > cw) return;

          let y1 = -10000; let y2 = 10000;
          if (data.startPrice !== undefined) { const sy = series.priceToCoordinate(data.startPrice); if (sy !== null) y1 = sy as number; }
          if (data.endPrice !== undefined) { const ey = series.priceToCoordinate(data.endPrice); if (ey !== null) y2 = ey as number; }

          target.useBitmapCoordinateSpace((scope: { context: CanvasRenderingContext2D }) => {
            const ctx = scope.context;
            ctx.save();
            ctx.beginPath(); ctx.moveTo(x as number, y1); ctx.lineTo(x as number, y2);
            ctx.strokeStyle = data.color; ctx.lineWidth = data.lineWidth;
            const dash = lineStyleToDash(data.lineStyle);
            if (dash.length > 0) ctx.setLineDash(dash); ctx.stroke();

            if (data.label) {
              ctx.font = "10px sans-serif"; ctx.fillStyle = data.color; ctx.textAlign = "center";
              const ly = data.labelPosition === "bottom" ? y2 + 14 : y1 - 6;
              ctx.textBaseline = data.labelPosition === "bottom" ? "top" : "bottom";
              ctx.fillText(data.label, x as number, ly);
            }
            ctx.restore();
          });
        },
      }),
    }];
  }

  updateData(partial: Partial<VerticalLineData>): void { Object.assign(this._data, partial); this._requestUpdate?.(); }
  getData(): Readonly<VerticalLineData> { return this._data; }
}
