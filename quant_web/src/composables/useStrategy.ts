// 策略相关业务逻辑
import { ref, computed } from "vue";
import { useStore } from "vuex";
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";
import signalsAPI from "@/api/signals";

export function useStrategy() {
  const store = useStore();

  const currentStrategy = ref<any>(null);
  const isStrategyRunning = ref(false);
  const strategyLogs = ref<string[]>([]);

  // 获取策略列表
  const getStrategyList = async () => {
    try {
      const strategies = await strategyAPI.getStrategies();
      store.commit("strategy/SET_STRATEGIES", strategies);
      return strategies;
    } catch (error) {
      console.error("获取策略列表失败:", error);
      throw error;
    }
  };

  // 创建策略
  const createStrategy = async (strategyData: {
    name: string;
    description: string;
    code: string;
    parameters: Record<string, any>;
    category?: string;
    tags?: string[];
  }) => {
    try {
      const strategy = await strategyAPI.createStrategy(strategyData);
      store.commit("strategy/ADD_STRATEGY", strategy);
      return strategy;
    } catch (error) {
      console.error("创建策略失败:", error);
      throw error;
    }
  };

  // 更新策略
  const updateStrategy = async (strategyId: string, updates: any) => {
    try {
      const strategy = await strategyAPI.updateStrategy(strategyId, updates);
      store.commit("strategy/UPDATE_STRATEGY", strategy);
      return strategy;
    } catch (error) {
      console.error("更新策略失败:", error);
      throw error;
    }
  };

  // 删除策略
  const deleteStrategy = async (strategyId: string) => {
    try {
      await strategyAPI.deleteStrategy(strategyId);
      store.commit("strategy/REMOVE_STRATEGY", strategyId);
    } catch (error) {
      console.error("删除策略失败:", error);
      throw error;
    }
  };

  // 启动策略
  const startStrategy = async (strategyId: string, params?: any) => {
    try {
      const status = await strategyAPI.startStrategy(strategyId, params);
      store.commit("strategy/UPDATE_STRATEGY_STATUS", {
        strategyId,
        status: "running",
      });
      isStrategyRunning.value = true;
      return status;
    } catch (error) {
      console.error("启动策略失败:", error);
      throw error;
    }
  };

  // 停止策略
  const stopStrategy = async (strategyId: string) => {
    try {
      await strategyAPI.stopStrategy(strategyId);
      store.commit("strategy/UPDATE_STRATEGY_STATUS", {
        strategyId,
        status: "stopped",
      });
      isStrategyRunning.value = false;
    } catch (error) {
      console.error("停止策略失败:", error);
      throw error;
    }
  };

  // 运行回测
  const runBacktest = async (
    strategyId: string,
    config: {
      start_date: string;
      end_date: string;
      initial_capital: number;
      universe: string[];
      parameters?: any;
    },
  ) => {
    try {
      const result = await backtestAPI.createTask({
        name: `回测_${strategyId}`,
        strategyId,
        startDate: config.start_date,
        endDate: config.end_date,
        initialCapital: config.initial_capital,
        commission: 0.0003,
        slippage: 0.01,
        universe: config.universe,
        parameters: config.parameters,
      } as any);

      store.commit("strategy/SET_BACKTEST_RESULT", {
        strategyId,
        result,
      });

      return result;
    } catch (error) {
      console.error("回测运行失败:", error);
      throw error;
    }
  };

  // 获取策略信号
  const getStrategySignals = async (strategyId: string, params?: any) => {
    try {
      const signals = await signalsAPI.getSignals({
        strategyId,
        ...params,
      } as any);
      store.commit("strategy/SET_STRATEGY_SIGNALS", {
        strategyId,
        signals,
      });
      return signals;
    } catch (error) {
      console.error("获取策略信号失败:", error);
      throw error;
    }
  };

  // 策略参数优化（回测模块中的参数优化）
  const optimizeStrategy = async (
    strategyId: string,
    optimizationConfig: {
      parameter_ranges: { [key: string]: [number, number] };
      optimization_method: "grid" | "genetic" | "bayesian";
      metric: "sharpe" | "max_drawdown" | "total_return";
    },
  ) => {
    try {
      // 参数优化通过回测 API 发起
      const result = await backtestAPI.optimizeParameters({
        strategyId,
        parameterRanges: optimizationConfig.parameter_ranges as any,
        optimizationTarget: optimizationConfig.metric,
        startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000)
          .toISOString()
          .split("T")[0],
        endDate: new Date().toISOString().split("T")[0],
        initialCapital: 1000000,
      } as any);
      return result;
    } catch (error) {
      console.error("策略参数优化失败:", error);
      throw error;
    }
  };

  // 实时监控策略性能
  const monitorStrategy = (strategyId: string) => {
    const interval = setInterval(async () => {
      try {
        const performance =
          await strategyAPI.getStrategyPerformance(strategyId);
        store.commit("strategy/UPDATE_STRATEGY_PERFORMANCE", {
          strategyId,
          performance,
        });
      } catch (error) {
        console.error("获取策略状态失败:", error);
      }
    }, 5000);

    return () => clearInterval(interval);
  };

  // 计算策略指标
  const calculateStrategyMetrics = (equityCurve: any[]) => {
    if (equityCurve.length < 2) return null;

    const returns = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const ret =
        (equityCurve[i].equity - equityCurve[i - 1].equity) /
        equityCurve[i - 1].equity;
      returns.push(ret);
    }

    const totalReturn =
      (equityCurve[equityCurve.length - 1].equity - equityCurve[0].equity) /
      equityCurve[0].equity;
    const annualReturn = totalReturn / (equityCurve.length / 252);

    const volatility = Math.sqrt(
      returns.reduce(
        (sum, ret) => sum + Math.pow(ret - totalReturn / returns.length, 2),
        0,
      ) / returns.length,
    );
    const annualVolatility = volatility * Math.sqrt(252);

    const sharpeRatio = annualReturn / annualVolatility;

    let maxDrawdown = 0;
    let peak = equityCurve[0].equity;
    for (const point of equityCurve) {
      if (point.equity > peak) {
        peak = point.equity;
      }
      const drawdown = (peak - point.equity) / peak;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return {
      totalReturn: totalReturn * 100,
      annualReturn: annualReturn * 100,
      volatility: volatility * 100,
      annualVolatility: annualVolatility * 100,
      sharpeRatio,
      maxDrawdown: maxDrawdown * 100,
    };
  };

  // 计算属性
  const strategyList = computed(() => store.state.strategy.strategies);
  const activeStrategies = computed(() =>
    store.state.strategy.strategies.filter((s: any) => s.status === "running"),
  );
  const strategyPerformance = computed(
    () => store.state.strategy.strategyPerformance,
  );

  return {
    currentStrategy,
    isStrategyRunning,
    strategyLogs,
    strategyList,
    activeStrategies,
    strategyPerformance,

    getStrategyList,
    createStrategy,
    updateStrategy,
    deleteStrategy,
    startStrategy,
    stopStrategy,
    runBacktest,
    getStrategySignals,
    optimizeStrategy,
    monitorStrategy,
    calculateStrategyMetrics,
  };
}
