// shared.ts - 共享类型定义
import { BacktestPosition, BacktestTrade, EquityPoint } from "@/types";

export interface StrategyPerformance {
  totalReturn: number;
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
}

export interface BacktestResult {
  taskId: string;
  strategyId: string;
  status: string;
  parameters: Record<string, any>;
  performance: StrategyPerformance;
  equityCurve: EquityPoint[];
  trades: BacktestTrade[];
  positions: BacktestPosition[];
  startedAt: string;
  completedAt: string;
}
