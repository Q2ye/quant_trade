/**
 * 计算简单移动平均线 (SMA)
 * @param data 价格数据数组
 * @param period 计算周期
 * @returns SMA数组
 */
export function calculateSMA(data: number[], period: number): (number | null)[] {
  if (!data || data.length < period) {
    return Array(data.length).fill(null);
  }

  const sma: number[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j];
    }
    sma.push(sum / period);
  }

  return Array(data.length - sma.length).fill(null).concat(sma);
}

/**
 * 计算指数移动平均线 (EMA)
 * @param data 价格数据数组
 * @param period 计算周期
 * @returns EMA数组
 */
export function calculateEMA(data: number[], period: number): (number | null)[] {
  if (!data || data.length < period) {
    return Array(data.length).fill(null);
  }

  const ema: number[] = [];
  const k = 2 / (period + 1);

  // 计算第一个EMA为SMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i];
  }
  ema[period - 1] = sum / period;

  // 计算后续EMA
  for (let i = period; i < data.length; i++) {
    ema[i] = data[i] * k + ema[i - 1] * (1 - k);
  }

  return ema;
}

interface MACDResult {
  dif: (number | null)[];
  dea: (number | null)[];
  macd: (number | null)[];
}

/**
 * 计算MACD指标
 * @param data 价格数据数组
 * @param fastPeriod 快线周期 (默认12)
 * @param slowPeriod 慢线周期 (默认26)
 * @param signalPeriod 信号线周期 (默认9)
 * @returns 包含DIF, DEA, MACD的对象
 */
export function calculateMACD(
  data: number[],
  fastPeriod = 12,
  slowPeriod = 26,
  signalPeriod = 9
): MACDResult {
  const fastEMA = calculateEMA(data, fastPeriod);
  const slowEMA = calculateEMA(data, slowPeriod);

  // 计算DIF
  const dif = fastEMA.map((fast, i) => {
    if (fast === null || slowEMA[i] === null) return null;
    return fast - slowEMA[i];
  });

  // 计算DEA (DIF的EMA)
  const dea = calculateEMA(dif.filter(d => d !== null) as number[], signalPeriod);

  // 计算MACD柱
  const macd = dif.map((d, i) => {
    if (d === null || dea[i] === null) return null;
    return (d - dea[i]) * 2;
  });

  return { dif, dea, macd };
}

interface BollingerBandsResult {
  middle: (number | null)[];
  upper: (number | null)[];
  lower: (number | null)[];
}

/**
 * 计算布林带指标
 * @param data 价格数据数组
 * @param period 计算周期 (默认20)
 * @param multiplier 标准差乘数 (默认2)
 * @returns 包含中轨、上轨、下轨的对象
 */
export function calculateBollingerBands(
  data: number[],
  period = 20,
  multiplier = 2
): BollingerBandsResult {
  if (!data || data.length < period) {
    return {
      middle: Array(data.length).fill(null),
      upper: Array(data.length).fill(null),
      lower: Array(data.length).fill(null)
    };
  }

  const middle: number[] = [];
  const upper: number[] = [];
  const lower: number[] = [];

  for (let i = period - 1; i < data.length; i++) {
    // 计算中轨 (SMA)
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j];
    }
    const sma = sum / period;
    middle.push(sma);

    // 计算标准差
    let variance = 0;
    for (let j = 0; j < period; j++) {
      variance += Math.pow(data[i - j] - sma, 2);
    }
    const stdDev = Math.sqrt(variance / period);

    // 计算上下轨
    upper.push(sma + multiplier * stdDev);
    lower.push(sma - multiplier * stdDev);
  }

  // 填充前期数据为null
  const padLength = data.length - middle.length;
  const padArray: null[] = Array(padLength).fill(null);

  return {
    middle: padArray.concat(middle),
    upper: padArray.concat(upper),
    lower: padArray.concat(lower)
  };
}

/**
 * 计算相对强弱指标 (RSI)
 * @param data 价格数据数组
 * @param period 计算周期 (默认14)
 * @returns RSI数组
 */
export function calculateRSI(data: number[], period = 14): (number | null)[] {
  if (!data || data.length < period + 1) {
    return Array(data.length).fill(null);
  }

  const rsi: number[] = [];
  const gains: number[] = [];
  const losses: number[] = [];

  // 计算初始变化值
  for (let i = 1; i <= period; i++) {
    const change = data[i] - data[i - 1];
    gains.push(change > 0 ? change : 0);
    losses.push(change < 0 ? Math.abs(change) : 0);
  }

  // 计算初始平均收益和平均损失
  let avgGain = gains.reduce((sum, gain) => sum + gain, 0) / period;
  let avgLoss = losses.reduce((sum, loss) => sum + loss, 0) / period;

  // 计算初始RS
  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  rsi.push(100 - (100 / (1 + rs)));

  // 计算后续RSI值
  for (let i = period + 1; i < data.length; i++) {
    const change = data[i] - data[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

    // 平滑计算平均收益和平均损失
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    // 计算RS和RSI
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(100 - (100 / (1 + rs)));
  }

  return Array(data.length - rsi.length).fill(null).concat(rsi);
}

interface KDJResult {
  k: (number | null)[];
  d: (number | null)[];
  j: (number | null)[];
}

/**
 * 计算随机指标 (KDJ)
 * @param high 最高价数组
 * @param low 最低价数组
 * @param close 收盘价数组
 * @param period KDJ计算周期 (默认9)
 * @returns 包含K, D, J值的对象
 */
export function calculateKDJ(
  high: number[],
  low: number[],
  close: number[],
  period = 9
): KDJResult {
  if (!high || !low || !close || high.length < period || low.length < period || close.length < period) {
    return {
      k: Array(close.length).fill(null),
      d: Array(close.length).fill(null),
      j: Array(close.length).fill(null)
    };
  }

  const kValues: number[] = [];
  const dValues: number[] = [];
  const jValues: number[] = [];

  // 计算RSV值
  const rsvValues: number[] = [];
  for (let i = period - 1; i < close.length; i++) {
    const highestHigh = Math.max(...high.slice(i - period + 1, i + 1));
    const lowestLow = Math.min(...low.slice(i - period + 1, i + 1));

    if (highestHigh === lowestLow) {
      rsvValues.push(50); // 防止除零错误
    } else {
      const rsv = ((close[i] - lowestLow) / (highestHigh - lowestLow)) * 100;
      rsvValues.push(rsv);
    }
  }

  // 计算K, D, J值
  let k = 50;
  let d = 50;

  for (let i = 0; i < rsvValues.length; i++) {
    k = (2/3) * k + (1/3) * rsvValues[i];
    d = (2/3) * d + (1/3) * k;
    const j = 3 * k - 2 * d;

    kValues.push(k);
    dValues.push(d);
    jValues.push(j);
  }

  // 填充前期数据为null
  const padLength = close.length - kValues.length;
  const padArray: null[] = Array(padLength).fill(null);

  return {
    k: padArray.concat(kValues),
    d: padArray.concat(dValues),
    j: padArray.concat(jValues)
  };
}