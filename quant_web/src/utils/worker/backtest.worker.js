 // 回测计算Worker
 // 回测计算Worker - 负责执行量化策略回测
importScripts('https://cdn.jsdelivr.net/npm/@quantlib/ql@latest/quantlib.min.js');

// 回测引擎状态
let backtestEngine = null;
let currentBacktestId = null;

// 监听主线程消息
self.addEventListener('message', (e) => {
  const { task, payload } = e.data;

  try {
    switch (task) {
      case 'INIT_BACKTEST':
        initBacktest(payload);
        break;

      case 'RUN_BACKTEST':
        runBacktest(payload);
        break;

      case 'PAUSE_BACKTEST':
        pauseBacktest();
        break;

      case 'RESUME_BACKTEST':
        resumeBacktest();
        break;

      case 'STOP_BACKTEST':
        stopBacktest();
        break;

      default:
        throw new Error(`Unknown task: ${task}`);
    }
  } catch (error) {
    self.postMessage({
      task: 'BACKTEST_ERROR',
      payload: {
        backtestId: currentBacktestId,
        error: error.message,
        stack: error.stack
      }
    });
  }
});

// 初始化回测引擎
function initBacktest(config) {
  currentBacktestId = config.backtestId;

  // 创建回测引擎实例
  backtestEngine = new BacktestEngine({
    data: config.data,
    strategy: config.strategyCode,
    initialCapital: config.capital,
    commission: config.commission,
    slippage: config.slippage,
    startDate: config.startDate,
    endDate: config.endDate,

    // 进度回调
    onProgress: (progress) => {
      self.postMessage({
        task: 'BACKTEST_PROGRESS',
        payload: {
          backtestId: currentBacktestId,
          progress,
          status: 'RUNNING'
        }
      });
    },

    // 交易信号回调
    onSignal: (signal) => {
      self.postMessage({
        task: 'BACKTEST_SIGNAL',
        payload: {
          backtestId: currentBacktestId,
          signal
        }
      });
    },

    // 交易执行回调
    onTrade: (trade) => {
      self.postMessage({
        task: 'BACKTEST_TRADE',
        payload: {
          backtestId: currentBacktestId,
          trade
        }
      });
    }
  });

  self.postMessage({
    task: 'BACKTEST_INITIALIZED',
    payload: { backtestId: currentBacktestId }
  });
}

// 运行回测
async function runBacktest() {
  if (!backtestEngine) {
    throw new Error('Backtest engine not initialized');
  }

  try {
    const results = await backtestEngine.run();

    self.postMessage({
      task: 'BACKTEST_COMPLETED',
      payload: {
        backtestId: currentBacktestId,
        results: {
          ...results,
          trades: backtestEngine.getTrades(),
          dailyPerformance: backtestEngine.getDailyPerformance()
        }
      }
    });
  } catch (error) {
    self.postMessage({
      task: 'BACKTEST_FAILED',
      payload: {
        backtestId: currentBacktestId,
        error: error.message
      }
    });
  }
}

// 暂停回测
function pauseBacktest() {
  if (backtestEngine) {
    backtestEngine.pause();
    self.postMessage({
      task: 'BACKTEST_PAUSED',
      payload: { backtestId: currentBacktestId }
    });
  }
}

// 恢复回测
function resumeBacktest() {
  if (backtestEngine) {
    backtestEngine.resume();
    self.postMessage({
      task: 'BACKTEST_RESUMED',
      payload: { backtestId: currentBacktestId }
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
      task: 'BACKTEST_STOPPED',
      payload: { backtestId: currentBacktestId }
    });
  }
}

// 回测引擎实现 (简化版)
class BacktestEngine {
  constructor(config) {
    this.config = config;
    this.data = config.data;
    this.strategy = this.compileStrategy(config.strategy);
    this.currentIndex = 0;
    this.isRunning = false;
    this.isPaused = false;
    this.trades = [];
    this.performance = [];
    this.signals = [];
  }

  // 编译策略函数
  compileStrategy(strategyCode) {
    try {
      // 在实际应用中，这里需要安全地编译策略代码
      const strategyFunc = new Function('ctx', strategyCode);

      // 返回策略执行函数
      return (ctx) => {
        try {
          return strategyFunc(ctx);
        } catch (error) {
          console.error('Strategy execution error:', error);
          return null;
        }
      };
    } catch (error) {
      throw new Error(`Strategy compilation failed: ${error.message}`);
    }
  }

  // 运行回测
  async run() {
    if (this.isRunning) {
      throw new Error('Backtest already running');
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
      portfolio: {}
    };

    // 主回测循环
    for (this.currentIndex = 0; this.currentIndex < this.data.length; this.currentIndex++) {
      if (!this.isRunning) break;

      // 处理暂停
      while (this.isPaused) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (!this.isRunning) break;
      }

      // 获取当前数据点
      const currentData = this.data[this.currentIndex];

      // 准备策略上下文
      const ctx = {
        data: this.data,
        index: this.currentIndex,
        state: this.state,
        indicators: this.state.indicators,
        portfolio: this.state.portfolio,
        current: currentData,
        history: this.data.slice(0, this.currentIndex + 1),
        emitSignal: (signal) => this.handleSignal(signal),
        executeOrder: (order) => this.executeOrder(order)
      };

      // 执行策略
      const result = this.strategy(ctx);

      // 更新每日表现
      this.updatePerformance(currentData);

      // 发送进度更新
      if (this.config.onProgress) {
        const progress = Math.round((this.currentIndex / this.data.length) * 100);
        this.config.onProgress(progress);
      }
    }

    // 计算最终结果
    const results = this.calculateResults();

    this.isRunning = false;
    return {
      ...results,
      executionTime: Date.now() - startTime,
      trades: this.trades,
      signals: this.signals
    };
  }

  // 处理策略信号
  handleSignal(signal) {
    const fullSignal = {
      ...signal,
      timestamp: new Date().toISOString(),
      backtestId: this.config.backtestId
    };

    this.signals.push(fullSignal);

    if (this.config.onSignal) {
      this.config.onSignal(fullSignal);
    }

    return fullSignal;
  }

  // 执行交易订单
  executeOrder(order) {
    const currentData = this.data[this.currentIndex];
    const tradePrice = order.type === 'MARKET' ?
      currentData.close :
      order.price;

    // 计算交易成本
    const commission = Math.max(
      this.config.commission * tradePrice * order.volume,
      5 // 最低佣金
    );

    const slippage = this.config.slippage * tradePrice * order.volume;
    const totalCost = tradePrice * order.volume + commission + slippage;

    // 创建交易记录
    const trade = {
      id: `trade_${this.trades.length + 1}`,
      ts_code: order.symbol,
      direction: order.direction,
      volume: order.volume,
      price: tradePrice,
      commission,
      slippage,
      totalCost,
      timestamp: currentData.trade_date,
      backtestId: this.config.backtestId
    };

    // 更新状态
    if (order.direction === 'BUY') {
      this.state.cash -= totalCost;
      this.state.position += order.volume;
    } else {
      this.state.cash += (tradePrice * order.volume) - commission - slippage;
      this.state.position -= order.volume;
    }

    this.trades.push(trade);

    if (this.config.onTrade) {
      this.config.onTrade(trade);
    }

    return trade;
  }

  // 更新每日表现
  updatePerformance(data) {
    const positionValue = this.state.position * data.close;
    this.state.equity = this.state.cash + positionValue;

    this.performance.push({
      date: data.trade_date,
      equity: this.state.equity,
      cash: this.state.cash,
      position: this.state.position,
      positionValue
    });
  }

  // 计算结果指标
  calculateResults() {
    if (this.performance.length === 0) {
      return {
        annualReturn: 0,
        sharpeRatio: 0,
        maxDrawdown: 0,
        winRate: 0,
        profitFactor: 1,
        totalTrades: this.trades.length
      };
    }

    // 计算累计收益
    const initialEquity = this.config.initialCapital;
    const finalEquity = this.performance[this.performance.length - 1].equity;
    const totalReturn = (finalEquity - initialEquity) / initialEquity;

    // 计算年化收益率
    const startDate = new Date(this.performance[0].date);
    const endDate = new Date(this.performance[this.performance.length - 1].date);
    const years = (endDate - startDate) / (1000 * 60 * 60 * 24 * 365.25);
    const annualReturn = Math.pow(1 + totalReturn, 1 / years) - 1;

    // 计算夏普比率
    const returns = this.calculateDailyReturns();
    const sharpeRatio = this.calculateSharpeRatio(returns);

    // 计算最大回撤
    const maxDrawdown = this.calculateMaxDrawdown();

    // 计算胜率和盈亏比
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
      dailyReturns: returns
    };
  }

  // 计算每日收益率
  calculateDailyReturns() {
    const returns = [];

    for (let i = 1; i < this.performance.length; i++) {
      const prev = this.performance[i - 1].equity;
      const current = this.performance[i].equity;
      returns.push((current - prev) / prev);
    }

    return returns;
  }

  // 计算夏普比率
  calculateSharpeRatio(dailyReturns) {
    const mean = dailyReturns.reduce((sum, ret) => sum + ret, 0) / dailyReturns.length;
    const variance = dailyReturns.reduce((sum, ret) => sum + Math.pow(ret - mean, 2), 0) / dailyReturns.length;
    const stdDev = Math.sqrt(variance);

    // 假设无风险利率为0
    return stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0;
  }

  // 计算最大回撤
  calculateMaxDrawdown() {
    let peak = this.performance[0].equity;
    let maxDrawdown = 0;

    for (const perf of this.performance) {
      if (perf.equity > peak) {
        peak = perf.equity;
      }

      const drawdown = (peak - perf.equity) / peak;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return maxDrawdown;
  }

  // 计算交易指标
  calculateTradeMetrics() {
    if (this.trades.length === 0) {
      return { winRate: 0, profitFactor: 1 };
    }

    let wins = 0;
    let totalProfit = 0;
    let totalLoss = 0;

    // 按交易对分组 (买入+卖出)
    for (let i = 0; i < this.trades.length; i += 2) {
      const buy = this.trades[i];
      const sell = this.trades[i + 1];

      if (buy && sell && buy.direction === 'BUY' && sell.direction === 'SELL') {
        const profit = (sell.price - buy.price) * buy.volume - buy.commission - sell.commission;

        if (profit > 0) {
          wins++;
          totalProfit += profit;
        } else {
          totalLoss += Math.abs(profit);
        }
      }
    }

    const winRate = wins / (this.trades.length / 2);
    const profitFactor = totalLoss > 0 ? totalProfit / totalLoss : 1;

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

  getTrades() {
    return [...this.trades];
  }

  getDailyPerformance() {
    return [...this.performance];
  }
}