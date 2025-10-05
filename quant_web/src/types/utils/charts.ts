// 图表相关类型定义

/**
 * 基础图表配置接口
 */
export interface ChartConfig {
  width?: number;           // 图表宽度
  height?: number;          // 图表高度
  theme?: 'light' | 'dark'; // 主题
  renderer?: 'canvas' | 'svg'; // 渲染方式
}

/**
 * K线图数据项接口
 */
export interface KLineData {
  timestamp: number;        // 时间戳
  open: number;             // 开盘价
  close: number;            // 收盘价
  high: number;             // 最高价
  low: number;              // 最低价
  volume: number;           // 成交量
  turnover?: number;        // 成交额
}

/**
 * 技术指标配置接口
 */
export interface IndicatorConfig {
  name: string;             // 指标名称 (MA, MACD, RSI等)
  period?: number;          // 周期参数
  color?: string;           // 显示颜色
  lineWidth?: number;       // 线宽
}

/**
 * 图表事件回调接口
 */
export interface ChartEvents {
  onChartClick?: (params: any) => void;           // 图表点击事件
  onDataZoom?: (params: any) => void;             // 数据缩放事件
  onLegendSelect?: (params: any) => void;         // 图例选择事件
}

/**
 * 净值曲线数据接口
 */
export interface EquityCurveData {
  date: string;            // 日期
  equity: number;          // 净值
  benchmark?: number;      // 基准净值
  drawdown?: number;       // 回撤
}

/**
 * 热力图数据接口
 */
export interface HeatmapData {
  x: string;               // X轴标签
  y: string;               // Y轴标签
  value: number;           // 数值
  itemStyle?: any;         // 样式配置
}

/**
 * 饼图数据项接口
 */
export interface PieDataItem {
  name: string;            // 名称
  value: number;           // 数值
  percentage?: number;     // 百分比
  itemStyle?: any;         // 样式配置
}

/**
 * 图表工具提示配置
 */
export interface TooltipConfig {
  trigger?: 'item' | 'axis' | 'none';  // 触发方式
  formatter?: string | ((params: any) => string); // 格式化函数
  backgroundColor?: string;             // 背景色
  borderColor?: string;                 // 边框色
}

/**
 * 坐标轴配置接口
 */
export interface AxisConfig {
  type?: 'value' | 'category' | 'time' | 'log'; // 坐标轴类型
  name?: string;                                // 坐标轴名称
  nameLocation?: 'start' | 'middle' | 'end';    // 名称位置
  min?: number | string;                        // 最小值
  max?: number | string;                        // 最大值
  scale?: boolean;                              // 是否脱离0值比例
}