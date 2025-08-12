import {formatDate} from './date';

export function parseStrategyCode(code) {
  // 解析策略代码中的参数和初始化函数
  const params = [];
  const initFunction = code.match(/def initializecontext:\s*([\s\S]*?)(?=def handle_data)/)?.[1];

  if (initFunction) {
    const paramMatches = initFunction.matchAll(/context\.(\w+)\s*=\s*([\d.]+)/g);
    for (const match of paramMatches) {
      params.push({
        name: match[1],
        value: parseFloat(match[2]),
        min: parseFloat(match[2]) * 0.5,
        max: parseFloat(match[2]) * 2,
        step: 1
      });
    }
  }

  return { params };
}
export function generateBacktestReportData(results) {
  return {
    summary: {
      initialCapital: results.initialCapital,
      finalValue: results.finalValue,
      totalReturn: (results.finalValue - results.initialCapital) / results.initialCapital,
      annualizedReturn: results.annualizedReturn,
      sharpeRatio: results.sharpeRatio,
      maxDrawdown: results.maxDrawdown,
      winRate: results.winRate,
      profitFactor: results.profitFactor
    },
    equityCurve: results.equityCurve.map(point => ({
      date: formatDate(point.date),
      value: point.value
    })),
    trades: results.trades.map(trade => ({
      id: trade.id,
      symbol: trade.symbol,
      direction: trade.direction,
      entryDate: formatDate(trade.entryDate),
      entryPrice: trade.entryPrice,
      exitDate: formatDate(trade.exitDate),
      exitPrice: trade.exitPrice,
      quantity: trade.quantity,
      profit: trade.profit,
      return: trade.return
    })),
    dailyReturns: results.dailyReturns.map(ret => ({
      date: formatDate(ret.date),
      return: ret.return
    }))
  };
}