// primitives/types.ts — 所有绘制原语的共享类型定义
// 核心约束：所有位置信息只存储时间戳和价格，绝不存储像素坐标
import type { Time } from "lightweight-charts";

/** 线型 */
export type LineStyle = 0 | 1 | 2 | 3 | 4; // Solid, Dashed, Dotted, DashedDotted, DashedDottedDotted

/** 趋势线数据 */
export interface TrendLineData {
  id: string;
  type: "trendLine";
  startTime: Time; // 'YYYY-MM-DD' 或 epoch seconds
  endTime: Time;
  startPrice: number;
  endPrice: number;
  lineColor: string;
  lineWidth: number;
  lineStyle: LineStyle;
  extendLeft: boolean; // 是否向左延长射线
  extendRight: boolean; // 是否向右延长射线
}

/** 信号标记方向 */
export type SignalDirection = "buy" | "sell";

/** 信号标记形状 */
export type SignalShape = "arrowUp" | "arrowDown" | "circle" | "square";

/** 信号标记数据 */
export interface SignalMarkerData {
  id: string;
  type: "signalMarker";
  time: Time;
  price: number;
  direction: SignalDirection;
  shape: SignalShape;
  color: string;
  text: string;
  strategyName?: string;
}

/** 水平线数据（支撑/阻力位） */
export interface HorizontalLineData {
  id: string;
  type: "horizontalLine";
  price: number;
  startTime?: Time; // 可选：限制线段的起始时间
  endTime?: Time; // 可选：限制线段的结束时间
  color: string;
  lineWidth: number;
  lineStyle: LineStyle;
  label?: string;
  labelPosition?: "left" | "right" | "center";
}

/** 垂直线数据（事件标记） */
export interface VerticalLineData {
  id: string;
  type: "verticalLine";
  time: Time;
  startPrice?: number; // 可选：限制线段的起始价格
  endPrice?: number; // 可选：限制线段的结束价格
  color: string;
  lineWidth: number;
  lineStyle: LineStyle;
  label?: string;
  labelPosition?: "top" | "bottom";
}

/** 文本标注数据 */
export interface AnnotationLabelData {
  id: string;
  type: "annotationLabel";
  time: Time;
  price: number;
  text: string;
  color: string;
  fontSize: number;
  fontFamily: string;
  backgroundColor?: string;
  borderColor?: string;
  offsetX?: number; // 像素偏移（仅用于微调，不参与定位）
  offsetY?: number;
}

/** 所有原语数据的联合类型 */
export type ChartPrimitiveData =
  | TrendLineData
  | SignalMarkerData
  | HorizontalLineData
  | VerticalLineData
  | AnnotationLabelData;

/** 用于可见性裁剪的原语最小信息 */
export interface PrimitiveVisibilityInfo {
  id: string;
  referenceTime: Time;
  endTime?: Time;
  alwaysVisible: boolean;
}
