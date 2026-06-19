// primitives/index.ts — 统一导出所有绘制原语
export { TrendLinePrimitive } from "./TrendLine";
export { SignalMarkerPrimitive } from "./SignalMarker";
export { HorizontalLinePrimitive } from "./HorizontalLine";
export { VerticalLinePrimitive } from "./VerticalLine";
export { AnnotationLabelPrimitive } from "./AnnotationLabel";

export type {
  TrendLineData,
  SignalMarkerData,
  HorizontalLineData,
  VerticalLineData,
  AnnotationLabelData,
  ChartPrimitiveData,
  SignalDirection,
  SignalShape,
  LineStyle,
} from "./types";
