// 策略相关业务逻辑
import { ref, computed } from 'vue'
import { useStore } from '@/store'
import { useApi } from '@/api/strategy'

export function useStrategy() {
  const store = useStore()
  const api = useApi()

  const currentStrategy = ref<any>(null)
  const isStrategyRunning = ref(false)
  const strategyLogs = ref<string[]>([])

  // 获取策略列表
  const getStrategyList = async () => {
    try {
      const response = await api.getStrategyList()
      store.commit('strategy/SET_STRATEGY_LIST', response.data)
      return response.data
    } catch (error) {
      console.error('获取策略列表失败:', error)
      throw error
    }
  }

  // 创建策略
  const createStrategy = async (strategyData: {
    name: string
    description: string
    class_name: string
    module_path: string
    parameters: any
  }) => {
    try {
      const response = await api.createStrategy(strategyData)
      store.commit('strategy/ADD_STRATEGY', response.data)
      return response.data
    } catch (error) {
      console.error('创建策略失败:', error)
      throw error
    }
  }

  // 更新策略
  const updateStrategy = async (strategyId: string, updates: any) => {
    try {
      const response = await api.updateStrategy(strategyId, updates)
      store.commit('strategy/UPDATE_STRATEGY', response.data)
      return response.data
    } catch (error) {
      console.error('更新策略失败:', error)
      throw error
    }
  }

  // 删除策略
  const deleteStrategy = async (strategyId: string) => {
    try {
      await api.deleteStrategy(strategyId)
      store.commit('strategy/REMOVE_STRATEGY', strategyId)
    } catch (error) {
      console.error('删除策略失败:', error)
      throw error
    }
  }

  // 启动策略
  const startStrategy = async (strategyId: string, params?: any) => {
    try {
      const response = await api.startStrategy(strategyId, params)
      store.commit('strategy/UPDATE_STRATEGY_STATUS', {
        strategyId,
        status: 'running'
      })
      isStrategyRunning.value = true
      return response.data
    } catch (error) {
      console.error('启动策略失败:', error)
      throw error
    }
  }

  // 停止策略
  const stopStrategy = async (strategyId: string) => {
    try {
      await api.stopStrategy(strategyId)
      store.commit('strategy/UPDATE_STRATEGY_STATUS', {
        strategyId,
        status: 'stopped'
      })
      isStrategyRunning.value = false
    } catch (error) {
      console.error('停止策略失败:', error)
      throw error
    }
  }

  // 运行回测
  const runBacktest = async (strategyId: string, config: {
    start_date: string
    end_date: string
    initial_capital: number
    universe: string[]
    parameters?: any
  }) => {
    try {
      const response = await api.runBacktest(strategyId, config)

      // 存储回测结果
      store.commit('strategy/SET_BACKTEST_RESULT', {
        strategyId,
        result: response.data
      })

      return response.data
    } catch (error) {
      console.error('回测运行失败:', error)
      throw error
    }
  }

  // 获取策略信号
  const getStrategySignals = async (strategyId: string, params?: any) => {
    try {
      const response = await api.getStrategySignals(strategyId, params)
      store.commit('strategy/SET_STRATEGY_SIGNALS', {
        strategyId,
        signals: response.data
      })
      return response.data
    } catch (error) {
      console.error('获取策略信号失败:', error)
      throw error
    }
  }

  // 策略参数优化
  const optimizeStrategy = async (strategyId: string, optimizationConfig: {
    parameter_ranges: { [key: string]: [number, number] }
    optimization_method: 'grid' | 'genetic' | 'bayesian'
    metric: 'sharpe' | 'max_drawdown' | 'total_return'
  }) => {
    try {
      const response = await api.optimizeStrategy(strategyId, optimizationConfig)
      return response.data
    } catch (error) {
      console.error('策略参数优化失败:', error)
      throw error
    }
  }

  // 实时监控策略性能
  const monitorStrategy = (strategyId: string) => {
    // 这里可以设置定时器或WebSocket监听来实时更新策略状态
    const interval = setInterval(async () => {
      try {
        const status = await api.getStrategyStatus(strategyId)
        store.commit('strategy/UPDATE_STRATEGY_PERFORMANCE', {
          strategyId,
          performance: status.data
        })
      } catch (error) {
        console.error('获取策略状态失败:', error)
      }
    }, 5000) // 每5秒更新一次

    return () => clearInterval(interval)
  }

  // 计算策略指标
  const calculateStrategyMetrics = (equityCurve: any[]) => {
    if (equityCurve.length < 2) return null

    const returns = []
    for (let i = 1; i < equityCurve.length; i++) {
      const ret = (equityCurve[i].equity - equityCurve[i-1].equity) / equityCurve[i-1].equity
      returns.push(ret)
    }

    const totalReturn = (equityCurve[equityCurve.length-1].equity - equityCurve[0].equity) / equityCurve[0].equity
    const annualReturn = totalReturn / (equityCurve.length / 252) // 假设252个交易日

    const volatility = Math.sqrt(returns.reduce((sum, ret) => sum + Math.pow(ret - totalReturn/returns.length, 2), 0) / returns.length)
    const annualVolatility = volatility * Math.sqrt(252)

    const sharpeRatio = annualReturn / annualVolatility

    let maxDrawdown = 0
    let peak = equityCurve[0].equity
    for (const point of equityCurve) {
      if (point.equity > peak) {
        peak = point.equity
      }
      const drawdown = (peak - point.equity) / peak
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown
      }
    }

    return {
      totalReturn: totalReturn * 100,
      annualReturn: annualReturn * 100,
      volatility: volatility * 100,
      annualVolatility: annualVolatility * 100,
      sharpeRatio,
      maxDrawdown: maxDrawdown * 100
    }
  }

  // 计算属性
  const strategyList = computed(() => store.state.strategy.strategyList)
  const activeStrategies = computed(() =>
    store.state.strategy.strategyList.filter(s => s.status === 'running')
  )
  const strategyPerformance = computed(() => store.state.strategy.strategyPerformance)

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
    calculateStrategyMetrics
  }
}