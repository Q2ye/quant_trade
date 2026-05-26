// quant_web/src/types/entities/dashboard.ts
/**
 * 仪表盘相关实体类型定义
 * 包含仪表盘展示所需的各种数据模型
 */

export interface DashboardData {
  totalAssets: number;
  dailyPnL: number;
  positionValue: number;
  availableCash: number;
  returnRate: number;
  performanceChart: PerformanceChartItem[];
  riskMatrix: RiskMatrix;
  realTimeSignals: RealTimeSignal[];
  marketSentiment: MarketSentiment;
  positions: Position[];
  todayTrades: Trade[];
}

export interface PerformanceChartItem {
  date: string;
  value: number;
  benchmark: number;
}

export interface RiskMatrix {
  positionDistribution: PositionDistribution[];
  industryExposure: IndustryExposure[];
  var: number;
}

export interface PositionDistribution {
  name: string;
  value: number;
  percentage: number;
}

export interface IndustryExposure {
  industry: string;
  exposure: number;
  concentration: number;
}

export interface RealTimeSignal {
  id: string;
  symbol: string;
  type: string;
  price: number;
  volume: number;
  timestamp: number;
  strength: number;
}

export interface MarketSentiment {
  advancing: number;
  declining: number;
  unchanged: number;
  volume: number;
  northbound: number;
  marketHeat: number;
}

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  avgCost: number;
  marketPrice: number;
  marketValue: number;
  pnl: number;
  pnlPercentage: number;
}

export interface Trade {
  id: string;
  symbol: string;
  direction: "buy" | "sell";
  price: number;
  volume: number;
  amount: number;
  tradeTime: string;
  commission: number;
}

export interface RealTimeDataEvent {
  type: string;
  symbol: string;
  data: any;
  timestamp: number;
}
