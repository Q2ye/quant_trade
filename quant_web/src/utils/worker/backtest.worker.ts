// events.worker.ts

// 声明 Web Worker 环境
declare function importScripts(...urls: string[]): void;

// 导入 QuantLib（如果可用）
try {
  importScripts(
    "https://cdn.misdeliver.net/npm/@quantlib/ql@latest/quantlib.min.js",
  );
} catch (error) {
  console.warn("QuantLib import failed, running without external library");
}

// 定义类型
type BacktestConfig = {
  backtestId: string;
  data: StockData[];
  strategyCode: string;
  capital: number;
  commission: number;
  slippage: number;
  startDate: string;
  endDate: string;
};

type BacktestResult = {
  initialCapital: number;
  finalEquity: number;
  totalReturn: number;
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  dailyReturns: number[];
  executionTime: number;
  trades: Trade[];
  dailyPerformance: PerformanceRecord[];
};

type Trade = {
  id: string;
  ts_code: string;
  direction: "BUY" | "SELL";
  volume: number;
  price: number;
  commission: number;
  slippage: number;
  totalCost: number;
  timestamp: string;
  backtestId: string;
};

type Signal = {
  symbol: string;
  type: string;
  strength: number;
  timestamp: string;
  backtestId: string;
};

type PerformanceRecord = {
  date: string;
  equity: number;
  cash: number;
  position: number;
  positionValue: number;
};

type BacktestEngineConfig = {
  data: StockData[];
  strategy: string;
  initialCapital: number;
  commission: number;
  slippage: number;
  startDate: string;
  endDate: string;
  backtestId?: string;
  onProgress?: (progress: number) => void;
  onSignal?: (signal: Signal) => void;
  onTrade?: (trade: Trade) => void;
};

// 回测引擎状态
let backtestEngine: BacktestEngine | null = null;
let currentBacktestId: string | null = null;

// 监听主线程消息
self.addEventListener(
  "message",
  (e: MessageEvent<{ task: string; payload: any }>) => {
    const { task, payload } = e.data;

    try {
      switch (task) {
        case "INIT_BACKTEST":
          initBacktest(payload);
          break;
        case "RUN_BACKTEST":
          runBacktest();
          break;
        case "PAUSE_BACKTEST":
          pauseBacktest();
          break;
        case "RESUME_BACKTEST":
          resumeBacktest();
          break;
        case "STOP_BACKTEST":
          stopBacktest();
          break;
        default:
          throw new Error(`Unknown task: ${task}`);
      }
    } catch (error: any) {
      self.postMessage({
        task: "BACKTEST_ERROR",
        payload: {
          backtestId: currentBacktestId,
          error: error.message,
          stack: error.stack,
        },
      });
    }
  },
);

// 初始化回测引擎
function initBacktest(config: BacktestConfig) {
  currentBacktestId = config.backtestId;

  backtestEngine = new BacktestEngine({
    data: config.data,
    strategy: config.strategyCode,
    initialCapital: config.capital,
    commission: config.commission,
    slippage: config.slippage,
    startDate: config.startDate,
    endDate: config.endDate,
    backtestId: config.backtestId,
    onProgress: (progress) => {
      self.postMessage({
        task: "BACKTEST_PROGRESS",
        payload: {
          backtestId: currentBacktestId,
          progress,
          status: "RUNNING",
        },
      });
    },
    onSignal: (signal) => {
      self.postMessage({
        task: "BACKTEST_SIGNAL",
        payload: {
          backtestId: currentBacktestId,
          signal,
        },
      });
    },
    onTrade: (trade) => {
      self.postMessage({
        task: "BACKTEST_TRADE",
        payload: {
          backtestId: currentBacktestId,
          trade,
        },
      });
    },
  });

  self.postMessage({
    task: "BACKTEST_INITIALIZED",
    payload: { backtestId: currentBacktestId },
  });
}

// 运行回测
async function runBacktest() {
  if (!backtestEngine) {
    throw new Error("Backtest engine not initialized");
  }

  try {
    const results = await backtestEngine.run();

    self.postMessage({
      task: "BACKTEST_COMPLETED",
      payload: {
        backtestId: currentBacktestId,
        results: {
          ...results,
          trades: backtestEngine.getTrades(),
          dailyPerformance: backtestEngine.getDailyPerformance(),
        },
      },
    });
  } catch (error: any) {
    self.postMessage({
      task: "BACKTEST_FAILED",
      payload: {
        backtestId: currentBacktestId,
        error: error.message,
      },
    });
  }
}

// 暂停回测
function pauseBacktest() {
  if (backtestEngine) {
    backtestEngine.pause();
    self.postMessage({
      task: "BACKTEST_PAUSED",
      payload: { backtestId: currentBacktestId },
    });
  }
}

// 恢复回测
function resumeBacktest() {
  if (backtestEngine) {
    backtestEngine.resume();
    self.postMessage({
      task: "BACKTEST_RESUMED",
      payload: { backtestId: currentBacktestId },
    });
  }
}

// 停止回测
function stopBacktest() {
  if (backtestEngine) {
    backtestEngine.stop();
    backtestEngine = null;
    currentBacktestId = null;
    self.postMessage({
      task: "BACKTEST_STOPPED",
      payload: { backtestId: currentBacktestId },
    });
  }
}

// 回测引擎实现
class BacktestEngine {
  private readonly config: BacktestEngineConfig;
  private readonly data: StockData[];
  private readonly strategy: (ctx: any) => any;
  private currentIndex: number;
  private isRunning: boolean;
  private isPaused: boolean;
  private readonly trades: Trade[];
  private readonly performance: PerformanceRecord[];
  private readonly signals: Signal[];
  private state: {
    position: number;
    cash: number;
    equity: number;
    indicators: Record<string, any>;
    portfolio: Record<string, any>;
  };

  constructor(config: BacktestEngineConfig) {
    this.config = config;
    this.data = config.data;
    this.strategy = this.compileStrategy(config.strategy);
    this.currentIndex = 0;
    this.isRunning = false;
    this.isPaused = false;
    this.trades = [];
    this.performance = [];
    this.signals = [];
    this.state = {
      position: 0,
      cash: 0,
      equity: 0,
      indicators: {},
      portfolio: {},
    };
  }

  private compileStrategy(strategyCode: string): (ctx: any) => any {
    try {
      // 使用正确的 Function 构造函数
      const strategyFunc = new Function("ctx", strategyCode);
      return (ctx: any) => {
        try {
          return strategyFunc(ctx);
        } catch (error: any) {
          console.error("Strategy execution error:", error);
          return null;
        }
      };
    } catch (error: any) {
      throw new Error(`Strategy compilation failed: ${error.message}`);
    }
  }

  async run(): Promise<BacktestResult> {
    if (this.isRunning) {
      throw new Error("Backtest already running");
    }

    this.isRunning = true;
    this.isPaused = false;
    const startTime = Date.now();

    // 初始化策略状态
    this.state = {
      position: 0,
      cash: this.config.initialCapital,
      equity: this.config.initialCapital,
      indicators: {},
      portfolio: {},
    };

    // 主回测循环
    for (
      this.currentIndex = 0;
      this.currentIndex < this.data.length;
      this.currentIndex++
    ) {
      if (!this.isRunning) break;

      // 处理暂停
      while (this.isPaused) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        if (!this.isRunning) break;
      }

      const currentData = this.data[this.currentIndex];
      const ctx = {
        data: this.data,
        index: this.currentIndex,
        state: this.state,
        indicators: this.state.indicators,
        portfolio: this.state.portfolio,
        current: currentData,
        history: this.data.slice(0, this.currentIndex + 1),
        emitSignal: (signal: any) => this.handleSignal(signal),
        executeOrder: (order: any) => this.executeOrder(order),
      };

      this.strategy(ctx);
      this.updatePerformance(currentData);

      if (this.config.onProgress) {
        const progress = Math.round(
          (this.currentIndex / this.data.length) * 100,
        );
        this.config.onProgress(progress);
      }
    }

    const results = this.calculateResults();
    this.isRunning = false;

    return {
      ...results,
      executionTime: Date.now() - startTime,
      trades: this.trades,
      dailyPerformance: this.performance,
    } as BacktestResult;
  }

  private handleSignal(signal: any): Signal {
    const fullSignal: Signal = {
      ...signal,
      timestamp: new Date().toISOString(),
      backtestId: this.config.backtestId || "",
    };

    this.signals.push(fullSignal);

    if (this.config.onSignal) {
      this.config.onSignal(fullSignal);
    }

    return fullSignal;
  }

  private executeOrder(order: any): Trade {
    const currentData = this.data[this.currentIndex];
    const tradePrice =
      order.type === "MARKET" ? currentData.close : order.price;
    const commission = Math.max(
      this.config.commission * tradePrice * order.volume,
      5,
    );
    const slippage = this.config.slippage * tradePrice * order.volume;
    const totalCost = tradePrice * order.volume + commission + slippage;

    const trade: Trade = {
      id: `trade_${this.trades.length + 1}`,
      ts_code: order.symbol,
      direction: order.direction,
      volume: order.volume,
      price: tradePrice,
      commission,
      slippage,
      totalCost,
      timestamp: currentData.trade_date,
      backtestId: this.config.backtestId || "",
    };

    if (order.direction === "BUY") {
      this.state.cash -= totalCost;
      this.state.position += order.volume;
    } else {
      this.state.cash += tradePrice * order.volume - commission - slippage;
      this.state.position -= order.volume;
    }

    this.trades.push(trade);

    if (this.config.onTrade) {
      this.config.onTrade(trade);
    }

    return trade;
  }

  private updatePerformance(data: StockData) {
    const positionValue = this.state.position * data.close;
    this.state.equity = this.state.cash + positionValue;

    this.performance.push({
      date: data.trade_date,
      equity: this.state.equity,
      cash: this.state.cash,
      position: this.state.position,
      positionValue,
    });
  }

  private calculateResults() {
    if (this.performance.length === 0) {
      return {
        initialCapital: this.config.initialCapital,
        finalEquity: this.config.initialCapital,
        totalReturn: 0,
        annualReturn: 0,
        sharpeRatio: 0,
        maxDrawdown: 0,
        winRate: 0,
        profitFactor: 1,
        totalTrades: this.trades.length,
        dailyReturns: [],
      };
    }

    const initialEquity = this.config.initialCapital;
    const finalEquity = this.performance[this.performance.length - 1].equity;
    const totalReturn = (finalEquity - initialEquity) / initialEquity;

    const startDate = new Date(this.performance[0].date);
    const endDate = new Date(
      this.performance[this.performance.length - 1].date,
    );
    const years =
      (endDate.getTime() - startDate.getTime()) /
      (1000 * 60 * 60 * 24 * 365.25);
    const annualReturn = Math.pow(1 + totalReturn, 1 / years) - 1;

    const returns = this.calculateDailyReturns();
    const sharpeRatio = this.calculateSharpeRatio(returns);
    const maxDrawdown = this.calculateMaxDrawdown();
    const { winRate, profitFactor } = this.calculateTradeMetrics();

    return {
      initialCapital: initialEquity,
      finalEquity,
      totalReturn,
      annualReturn,
      sharpeRatio,
      maxDrawdown,
      winRate,
      profitFactor,
      totalTrades: this.trades.length,
      dailyReturns: returns,
    };
  }

  private calculateDailyReturns(): number[] {
    const returns: number[] = [];
    for (let i = 1; i < this.performance.length; i++) {
      const prev = this.performance[i - 1].equity;
      const current = this.performance[i].equity;
      returns.push((current - prev) / prev);
    }
    return returns;
  }

  private calculateSharpeRatio(dailyReturns: number[]): number {
    if (dailyReturns.length === 0) return 0;

    const mean =
      dailyReturns.reduce((sum, ret) => sum + ret, 0) / dailyReturns.length;
    const variance =
      dailyReturns.reduce((sum, ret) => sum + Math.pow(ret - mean, 2), 0) /
      dailyReturns.length;
    const stdDev = Math.sqrt(variance);
    return stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0;
  }

  private calculateMaxDrawdown(): number {
    let peak = this.performance[0].equity;
    let maxDrawdown = 0;

    for (const perf of this.performance) {
      if (perf.equity > peak) peak = perf.equity;
      const drawdown = (peak - perf.equity) / peak;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    return maxDrawdown;
  }

  private calculateTradeMetrics(): { winRate: number; profitFactor: number } {
    if (this.trades.length === 0) {
      return { winRate: 0, profitFactor: 1 };
    }

    let wins = 0;
    let totalProfit = 0;
    let totalLoss = 0;

    for (let i = 0; i < this.trades.length; i += 2) {
      const buy = this.trades[i];
      const sell = this.trades[i + 1];

      if (buy && sell && buy.direction === "BUY" && sell.direction === "SELL") {
        const profit =
          (sell.price - buy.price) * buy.volume -
          buy.commission -
          sell.commission;

        if (profit > 0) {
          wins++;
          totalProfit += profit;
        } else {
          totalLoss += Math.abs(profit);
        }
      }
    }

    const winRate =
      this.trades.length > 0 ? wins / (this.trades.length / 2) : 0;
    const profitFactor =
      totalLoss > 0 ? totalProfit / totalLoss : totalProfit > 0 ? Infinity : 1;

    return { winRate, profitFactor };
  }

  pause() {
    this.isPaused = true;
  }

  resume() {
    this.isPaused = false;
  }

  stop() {
    this.isRunning = false;
    this.isPaused = false;
  }

  getTrades(): Trade[] {
    return [...this.trades];
  }

  getDailyPerformance(): PerformanceRecord[] {
    return [...this.performance];
  }
}
