import { formatDate } from "./date";

interface StrategyParam {
  name: string;
  value: number;
  min: number;
  max: number;
  step: number;
}

export function parseStrategyCode(code: string): { params: StrategyParam[] } {
  const params: StrategyParam[] = [];
  const initFunction = code.match(
    /def initializecontext:\s*([\s\S]*?)(?=def handle_data)/,
  )?.[1];

  if (initFunction) {
    const paramMatches = initFunction.matchAll(
      /context\.(\w+)\s*=\s*([\d.]+)/g,
    );
    for (const match of paramMatches) {
      const name = match[1];
      const value = parseFloat(match[2]);
      params.push({
        name,
        value,
        min: value * 0.5,
        max: value * 2,
        step: 1,
      });
    }
  }

  return { params };
}

interface BacktestTrade {
  id: string;
  symbol: string;
  direction: string;
  entryDate: Date | string;
  entryPrice: number;
  exitDate: Date | string;
  exitPrice: number;
  quantity: number;
  profit: number;
  return: number;
}

interface BacktestResults {
  initialCapital: number;
  finalValue: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  equityCurve: Array<{ date: Date | string; value: number }>;
  trades: BacktestTrade[];
  dailyReturns: Array<{ date: Date | string; return: number }>;
}

export function generateBacktestReportData(results: BacktestResults): any {
  return {
    summary: {
      initialCapital: results.initialCapital,
      finalValue: results.finalValue,
      totalReturn:
        (results.finalValue - results.initialCapital) / results.initialCapital,
      annualizedReturn: results.annualizedReturn,
      sharpeRatio: results.sharpeRatio,
      maxDrawdown: results.maxDrawdown,
      winRate: results.winRate,
      profitFactor: results.profitFactor,
    },
    equityCurve: results.equityCurve.map((point) => ({
      date: formatDate(point.date),
      value: point.value,
    })),
    trades: results.trades.map((trade) => ({
      id: trade.id,
      symbol: trade.symbol,
      direction: trade.direction,
      entryDate: formatDate(trade.entryDate),
      entryPrice: trade.entryPrice,
      exitDate: formatDate(trade.exitDate),
      exitPrice: trade.exitPrice,
      quantity: trade.quantity,
      profit: trade.profit,
      return: trade.return,
    })),
    dailyReturns: results.dailyReturns.map((ret) => ({
      date: formatDate(ret.date),
      return: ret.return,
    })),
  };
}
