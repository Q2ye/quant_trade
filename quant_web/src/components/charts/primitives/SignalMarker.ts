// SignalMarker.ts — 信号标记原语（替代 v5.2 被移除的 setMarkers API）
import {
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type PriceToCoordinateConverter,
} from "lightweight-charts";
import type { SignalMarkerData, SignalShape } from "./types";

const ARROW_SIZE = 8;
const CIRCLE_RADIUS = 5;

function drawArrowUp(ctx: CanvasRenderingContext2D, x: number, y: number, c: string): void {
  ctx.fillStyle = c;
  ctx.beginPath();
  ctx.moveTo(x, y - ARROW_SIZE);
  ctx.lineTo(x + ARROW_SIZE * 0.7, y);
  ctx.lineTo(x - ARROW_SIZE * 0.7, y);
  ctx.closePath();
  ctx.fill();
}
function drawArrowDown(ctx: CanvasRenderingContext2D, x: number, y: number, c: string): void {
  ctx.fillStyle = c;
  ctx.beginPath();
  ctx.moveTo(x, y + ARROW_SIZE);
  ctx.lineTo(x + ARROW_SIZE * 0.7, y);
  ctx.lineTo(x - ARROW_SIZE * 0.7, y);
  ctx.closePath();
  ctx.fill();
}
function drawCircle(ctx: CanvasRenderingContext2D, x: number, y: number, c: string): void {
  ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x, y, CIRCLE_RADIUS, 0, Math.PI * 2); ctx.fill();
}
function drawSquare(ctx: CanvasRenderingContext2D, x: number, y: number, c: string): void {
  const h = CIRCLE_RADIUS; ctx.fillStyle = c; ctx.fillRect(x - h, y - h, h * 2, h * 2);
}
function drawShape(ctx: CanvasRenderingContext2D, s: SignalShape, x: number, y: number, c: string): void {
  switch (s) {
    case "arrowUp": drawArrowUp(ctx, x, y, c); break;
    case "arrowDown": drawArrowDown(ctx, x, y, c); break;
    case "circle": drawCircle(ctx, x, y, c); break;
    case "square": drawSquare(ctx, x, y, c); break;
  }
}

export class SignalMarkerPrimitive implements ISeriesPrimitive<Time> {
  _chart: import("lightweight-charts").IChartApi | null = null;
  _data: SignalMarkerData;
  private _requestUpdate: (() => void) | null = null;

  constructor(data: SignalMarkerData) {
    this._data = { ...data };
  }

  attached(params: SeriesAttachedParameter<Time>): void {
    this._chart = params.chart;
    this._requestUpdate = params.requestUpdate;
  }

  detached(): void { this._chart = null; this._requestUpdate = null; }
  updateAllViews(): void { this._requestUpdate?.(); }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  paneViews(): any {
    const self = this;
    return [{
      zOrder: () => "top" as const,
      renderer: () => ({
        draw(target: any, priceConverter: PriceToCoordinateConverter, _isHovered: boolean, _hitTestData?: unknown): void {
          const chart = self._chart;
          const data = self._data;
          if (!chart) return;
          const x = chart.timeScale().timeToCoordinate(data.time);
          const y = priceConverter(data.price);
          if (x === null || y === null) return;
          const cw = chart.timeScale().width();
          if ((x as number) < 0 || (x as number) > cw) return;

          target.useBitmapCoordinateSpace((scope: { context: CanvasRenderingContext2D }) => {
            const ctx = scope.context;
            ctx.save();
            drawShape(ctx, data.shape, x as number, y as number, data.color);
            if (data.text) {
              ctx.font = "10px sans-serif"; ctx.fillStyle = data.color; ctx.textAlign = "center";
              const ty = data.direction === "buy" ? (y as number) - ARROW_SIZE - 4 : (y as number) + ARROW_SIZE + 14;
              ctx.fillText(data.text, x as number, ty);
            }
            if (data.strategyName) {
              ctx.font = "8px sans-serif"; ctx.fillStyle = "rgba(160,160,160,0.8)"; ctx.textAlign = "center";
              const stY = data.direction === "buy" ? (y as number) - ARROW_SIZE - 18 : (y as number) + ARROW_SIZE + 26;
              ctx.fillText(data.strategyName, x as number, stY);
            }
            ctx.restore();
          });
        },
      }),
    }];
  }

  updateData(partial: Partial<SignalMarkerData>): void { Object.assign(this._data, partial); this._requestUpdate?.(); }
  getData(): Readonly<SignalMarkerData> { return this._data; }
}
