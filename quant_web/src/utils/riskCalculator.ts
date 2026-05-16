interface EquityPoint {
  date: Date | string;
  value: number;
}

export function calculateMaxDrawdown(equityCurve: EquityPoint[]): number {
  let peak = -Infinity;
  let maxDrawdown = 0;

  for (const point of equityCurve) {
    if (point.value > peak) {
      peak = point.value;
    }

    const drawdown = (peak - point.value) / peak;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }

  return maxDrawdown;
}

export function calculateVolatility(returns: number[]): number {
  const mean = returns.reduce((sum, ret) => sum + ret, 0) / returns.length;
  const variance =
    returns.reduce((sum, ret) => sum + Math.pow(ret - mean, 2), 0) /
    returns.length;
  return Math.sqrt(variance);
}

export function calculateBeta(
  portfolioReturns: number[],
  benchmarkReturns: number[],
): number {
  if (portfolioReturns.length !== benchmarkReturns.length) {
    throw new Error("Returns arrays must have the same length");
  }

  const n = portfolioReturns.length;
  let sumPortfolio = 0;
  let sumBenchmark = 0;
  let sumPortfolioBenchmark = 0;
  let sumBenchmarkSquared = 0;

  for (let i = 0; i < n; i++) {
    sumPortfolio += portfolioReturns[i];
    sumBenchmark += benchmarkReturns[i];
    sumPortfolioBenchmark += portfolioReturns[i] * benchmarkReturns[i];
    sumBenchmarkSquared += Math.pow(benchmarkReturns[i], 2);
  }

  const cov = (sumPortfolioBenchmark - (sumPortfolio * sumBenchmark) / n) / n;
  const varBenchmark =
    (sumBenchmarkSquared - Math.pow(sumBenchmark, 2) / n) / n;

  return cov / varBenchmark;
}
