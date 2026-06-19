// HorizontalLine.ts — 水平线原语（支撑/阻力位、价格目标线）
import {
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type PriceToCoordinateConverter,
} from "lightweight-charts";
import type { HorizontalLineData, LineStyle } from "./types";

function lineStyleToDash(style: LineStyle): number[] {
  switch (style) {
    case 0: return []; case 1: return [6, 3]; case 2: return [2, 2];
    case 3: return [8, 3, 2, 3]; case 4: return [8, 3, 2, 3, 2, 3]; default: return [];
  }
}

const LP = 4; // label padding

export class HorizontalLinePrimitive implements ISeriesPrimitive<Time> {
  _chart: import("lightweight-charts").IChartApi | null = null;
  _data: HorizontalLineData;
  private _requestUpdate: (() => void) | null = null;

  constructor(data: HorizontalLineData) { this._data = { ...data }; }

  attached(params: SeriesAttachedParameter<Time>): void {
    this._chart = params.chart; this._requestUpdate = params.requestUpdate;
  }

  detached(): void { this._chart = null; this._requestUpdate = null; }
  updateAllViews(): void { this._requestUpdate?.(); }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  paneViews(): any {
    const self = this;
    return [{
      zOrder: () => "normal" as const,
      renderer: () => ({
        draw(target: any, priceConverter: PriceToCoordinateConverter, _isHovered: boolean, _hitTestData?: unknown): void {
          const chart = self._chart;
          const data = self._data;
          if (!chart) return;
          const ts = chart.timeScale();
          const cw = ts.width();
          const y = priceConverter(data.price);
          if (y === null) return;

          let x1 = 0; let x2 = cw;
          if (data.startTime) { const sx = ts.timeToCoordinate(data.startTime); if (sx !== null) x1 = Math.max(0, sx as number); }
          if (data.endTime) { const ex = ts.timeToCoordinate(data.endTime); if (ex !== null) x2 = Math.min(cw, ex as number); }
          if (x1 > cw || x2 < 0) return;

          target.useBitmapCoordinateSpace((scope: { context: CanvasRenderingContext2D }) => {
            const ctx = scope.context;
            ctx.save();
            ctx.beginPath(); ctx.moveTo(x1, y as number); ctx.lineTo(x2, y as number);
            ctx.strokeStyle = data.color; ctx.lineWidth = data.lineWidth;
            const dash = lineStyleToDash(data.lineStyle);
            if (dash.length > 0) ctx.setLineDash(dash); ctx.stroke();

            if (data.label) {
              ctx.font = "10px sans-serif"; ctx.fillStyle = data.color; ctx.textBaseline = "bottom";
              let lx: number;
              switch (data.labelPosition ?? "right") {
                case "left": lx = x1 + LP; ctx.textAlign = "left"; break;
                case "center": lx = (x1 + x2) / 2; ctx.textAlign = "center"; break;
                default: lx = x2 - LP; ctx.textAlign = "right"; break;
              }
              ctx.fillText(data.label, lx, (y as number) - 2);
            }
            ctx.restore();
          });
        },
      }),
    }];
  }

  updateData(partial: Partial<HorizontalLineData>): void { Object.assign(this._data, partial); this._requestUpdate?.(); }
  getData(): Readonly<HorizontalLineData> { return this._data; }
}
