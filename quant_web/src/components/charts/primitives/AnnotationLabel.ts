// AnnotationLabel.ts — 文本标注原语
import {
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type PriceToCoordinateConverter,
} from "lightweight-charts";
import type { AnnotationLabelData } from "./types";

const DX = 6; const DY = -12; const BPH = 4; const BPV = 2; const BR = 3;

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r); ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r); ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r); ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r); ctx.closePath();
}

export class AnnotationLabelPrimitive implements ISeriesPrimitive<Time> {
  _chart: import("lightweight-charts").IChartApi | null = null;
  _series: import("lightweight-charts").ISeriesApi<"Line", Time> | null = null;
  _data: AnnotationLabelData;
  private _requestUpdate: (() => void) | null = null;

  constructor(data: AnnotationLabelData) { this._data = { ...data }; }

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
      zOrder: () => "top" as const,
      renderer: () => ({
        draw(target: any, _utils?: unknown): void {
          const chart = self._chart;
          const series = self._series;
          const data = self._data;
          if (!chart || !series) return;
          const ts = chart.timeScale();
          const x = ts.timeToCoordinate(data.time);
          const y = series.priceToCoordinate(data.price);
          if (x === null || y === null) return;
          const cw = ts.width();
          if ((x as number) < 0 || (x as number) > cw) return;

          const lx = (x as number) + (data.offsetX ?? DX);
          const ly = (y as number) + (data.offsetY ?? DY);

          target.useBitmapCoordinateSpace((scope: { context: CanvasRenderingContext2D }) => {
            const ctx = scope.context;
            ctx.save();
            ctx.font = `${data.fontSize}px ${data.fontFamily}`;
            const tm = ctx.measureText(data.text);
            const tw = tm.width; const th = data.fontSize;

            if (data.backgroundColor) {
              const bx = lx - BPH; const by = ly - th - BPV;
              const bw = tw + BPH * 2; const bh = th + BPV * 2;
              ctx.fillStyle = data.backgroundColor;
              roundRect(ctx, bx, by, bw, bh, BR);
              ctx.fill();
              if (data.borderColor) { ctx.strokeStyle = data.borderColor; ctx.lineWidth = 1; ctx.stroke(); }
            }

            ctx.fillStyle = data.color; ctx.textAlign = "left"; ctx.textBaseline = "bottom";
            ctx.fillText(data.text, lx, ly);
            ctx.restore();
          });
        },
      }),
    }];
  }

  updateData(partial: Partial<AnnotationLabelData>): void { Object.assign(this._data, partial); this._requestUpdate?.(); }
  getData(): Readonly<AnnotationLabelData> { return this._data; }
}
