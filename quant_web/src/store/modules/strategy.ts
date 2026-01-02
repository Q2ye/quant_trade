// quant_web/src/store/modules/events.ts
// 策略管理Vuex模块
// 负责管理策略的创建、编辑、回测、执行等操作的状态
import { Module } from 'vuex'
import { RootState } from "@/types";
import {
  Strategy,
  StrategyRun,
  BacktestResult,
  TradeSignal,
  StrategyPerformance,
  StrategyStatusInfo
} from '@/types/entities/strategy';

/**
 * 策略模块状态接口
 */
export interface StrategyState {
  // 策略列表
  strategies: Strategy[]
  strategiesMap: Map<string, Strategy>

  // 当前选中的策略
  currentStrategy: Strategy | null

  // 策略运行状态
  strategyRuns: Map<string, StrategyRun[]>
  activeStrategies: Set<string> // 正在运行的策略ID

  // 回测结果
  backtestResults: Map<string, BacktestResult>
  currentBacktest: string | null // 当前查看的回测ID

  // 策略信号
  strategySignals: Map<string, TradeSignal[]>

  // 策略绩效
  strategyPerformance: Map<string, StrategyPerformance>

  // 加载状态
  isLoading: boolean
  lastUpdate: number
}

const state: StrategyState = {
  strategies: [],
  strategiesMap: new Map(),
  currentStrategy: null,
  strategyRuns: new Map(),
  activeStrategies: new Set(),
  backtestResults: new Map(),
  currentBacktest: null,
  strategySignals: new Map(),
  strategyPerformance: new Map(),
  isLoading: false,
  lastUpdate: 0
}

const mutations = {
  /**
   * 设置策略列表
   */
  SET_STRATEGIES(state: StrategyState, strategies: Strategy[]) {
    state.strategies = strategies
    state.strategiesMap = new Map(strategies.map(s => [s.id, s]))
  },

  /**
   * 添加策略
   */
  ADD_STRATEGY(state: StrategyState, strategy: Strategy) {
    state.strategies.push(strategy)
    state.strategiesMap.set(strategy.id, strategy)
  },

  /**
   * 更新策略
   */
  UPDATE_STRATEGY(state: StrategyState, strategy: Strategy) {
    const index = state.strategies.findIndex(s => s.id === strategy.id)
    if (index !== -1) {
      state.strategies.splice(index, 1, strategy)
    }
    state.strategiesMap.set(strategy.id, strategy)
  },

  /**
   * 删除策略
   */
  REMOVE_STRATEGY(state: StrategyState, strategyId: string) {
    state.strategies = state.strategies.filter(s => s.id !== strategyId)
    state.strategiesMap.delete(strategyId)
    state.strategyRuns.delete(strategyId)
    state.backtestResults.delete(strategyId)
    state.strategySignals.delete(strategyId)
    state.strategyPerformance.delete(strategyId)
    state.activeStrategies.delete(strategyId)
  },

  /**
   * 设置当前策略
   */
  SET_CURRENT_STRATEGY(state: StrategyState, strategy: Strategy | null) {
    state.currentStrategy = strategy
  },

  /**
   * 更新策略状态
   */
  UPDATE_STRATEGY_STATUS(state: StrategyState, payload: { strategyId: string; status: 'running' | 'stopped' | 'error' }) {
    const strategy = state.strategiesMap.get(payload.strategyId)
    if (strategy) {
      strategy.status = payload.status

      if (payload.status === 'running') {
        state.activeStrategies.add(payload.strategyId)
      } else {
        state.activeStrategies.delete(payload.strategyId)
      }
    }
  },

  /**
   * 添加策略运行记录
   */
  ADD_STRATEGY_RUN(state: StrategyState, payload: { strategyId: string; run: StrategyRun }) {
    if (!state.strategyRuns.has(payload.strategyId)) {
      state.strategyRuns.set(payload.strategyId, [])
    }
    state.strategyRuns.get(payload.strategyId)!.push(payload.run)
  },

  /**
   * 设置回测结果
   */
  SET_BACKTEST_RESULT(state: StrategyState, payload: { strategyId: string; result: BacktestResult }) {
    state.backtestResults.set(payload.strategyId, payload.result)
  },

  /**
   * 设置当前回测
   */
  SET_CURRENT_BACKTEST(state: StrategyState, backtestId: string | null) {
    state.currentBacktest = backtestId
  },

  /**
   * 添加策略信号
   */
  ADD_STRATEGY_SIGNAL(state: StrategyState, signal: TradeSignal) {
    if (!state.strategySignals.has(signal.strategy_id)) {
      state.strategySignals.set(signal.strategy_id, [])
    }

    const signals = state.strategySignals.get(signal.strategy_id)!
    signals.unshift(signal) // 新的信号放在前面

    // 保持最多1000个信号
    if (signals.length > 1000) {
      signals.splice(1000)
    }
  },

  /**
   * 设置策略信号列表
   */
  SET_STRATEGY_SIGNALS(state: StrategyState, payload: { strategyId: string; signals: TradeSignal[] }) {
    state.strategySignals.set(payload.strategyId, payload.signals)
  },

  /**
   * 更新策略绩效
   */
  UPDATE_STRATEGY_PERFORMANCE(state: StrategyState, payload: { strategyId: string; performance: StrategyPerformance }) {
    state.strategyPerformance.set(payload.strategyId, payload.performance)
  },

  /**
   * 设置加载状态
   */
  SET_LOADING(state: StrategyState, loading: boolean) {
    state.isLoading = loading
  },

  /**
   * 清理过期信号（超过24小时）
   */
  CLEANUP_OLD_SIGNALS(state: StrategyState) {
    const twentyFourHoursAgo = Date.now() - 24 * 60 * 60 * 1000

    for (const [strategyId, signals] of state.strategySignals.entries()) {
      const filtered = signals.filter(signal =>
        new Date(signal.signal_time).getTime() > twentyFourHoursAgo
      )
      state.strategySignals.set(strategyId, filtered)
    }
  }
}

const actions = {
  /**
   * 加载策略列表
   */
  async loadStrategies({ commit, rootState }: any) {
    if (!rootState.user.isAuthenticated) {
      throw new Error('请先登录')
    }

    commit('SET_LOADING', true)
    try {
      const response = await fetch('/api/strategies', {
        headers: {
          'Authorization': `Bearer ${rootState.user.token}`
        }
      })
      const strategies = await response.json()
      commit('SET_STRATEGIES', strategies)
      commit('SET_LOADING', false)
    } catch (error) {
      console.error('加载策略列表失败:', error)
      commit('SET_LOADING', false)
      throw error
    }
  },

  /**
   * 创建策略
   */
  async createStrategy({ commit, rootState }: any, strategyData: Partial<Strategy>) {
    if (!rootState.user.isAuthenticated) {
      throw new Error('请先登录')
    }

    try {
      const response = await fetch('/api/strategies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${rootState.user.token}`
        },
        body: JSON.stringify(strategyData)
      })
      const strategy = await response.json()
      commit('ADD_STRATEGY', strategy)
      return strategy
    } catch (error) {
      console.error('创建策略失败:', error)
      throw error
    }
  },

  /**
   * 更新策略
   */
  async updateStrategy({ commit, rootState }: any, { strategyId, updates }: { strategyId: string; updates: Partial<Strategy> }) {
    try {
      const response = await fetch(`/api/strategies/${strategyId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${rootState.user.token}`
        },
        body: JSON.stringify(updates)
      })
      const strategy = await response.json()
      commit('UPDATE_STRATEGY', strategy)
      return strategy
    } catch (error) {
      console.error('更新策略失败:', error)
      throw error
    }
  },

  /**
   * 删除策略
   */
  async deleteStrategy({ commit, rootState }: any, strategyId: string) {
    try {
      await fetch(`/api/strategies/${strategyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${rootState.user.token}`
        }
      })
      commit('REMOVE_STRATEGY', strategyId)
    } catch (error) {
      console.error('删除策略失败:', error)
      throw error
    }
  },

  /**
   * 启动策略
   */
  async startStrategy({ commit, rootState }: any, { strategyId, params }: { strategyId: string; params?: any }) {
    try {
      const response = await fetch(`/api/strategies/${strategyId}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${rootState.user.token}`
        },
        body: JSON.stringify(params || {})
      })

      if (response.ok) {
        commit('UPDATE_STRATEGY_STATUS', { strategyId, status: 'running' })

        // 添加运行记录
        const run: StrategyRun = {
          id: `run_${Date.now()}`,
          strategy_id: strategyId,
          started_at: new Date().toISOString(),
          status: 'running',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
        commit('ADD_STRATEGY_RUN', { strategyId, run })
      }
    } catch (error) {
      console.error('启动策略失败:', error)
      throw error
    }
  },

  /**
   * 停止策略
   */
  async stopStrategy({ commit, rootState, state }: any, strategyId: string) {
    try {
      const response = await fetch(`/api/strategies/${strategyId}/stop`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${rootState.user.token}`
        }
      })

      if (response.ok) {
        commit('UPDATE_STRATEGY_STATUS', { strategyId, status: 'stopped' })

        // 更新运行记录
        const runs = state.strategyRuns.get(strategyId) || []
        const currentRun = runs.find((run: StrategyRun) => run.status === 'running')
        if (currentRun) {
          currentRun.status = 'stopped'
          currentRun.stopped_at = new Date().toISOString()
          currentRun.updated_at = new Date().toISOString()
        }
      }
    } catch (error) {
      console.error('停止策略失败:', error)
      throw error
    }
  },

  /**
   * 运行回测
   */
  async runBacktest({ commit, rootState }: any, { strategyId, config }: { strategyId: string; config: any }) {
    try {
      const response = await fetch(`/api/strategies/${strategyId}/backtest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${rootState.user.token}`
        },
        body: JSON.stringify(config)
      })
      const result = await response.json()
      commit('SET_BACKTEST_RESULT', { strategyId, result })
      return result
    } catch (error) {
      console.error('运行回测失败:', error)
      throw error
    }
  },

  /**
   * 获取策略信号
   */
  async loadStrategySignals({ commit, rootState }: any, { strategyId, limit = 100 }: { strategyId: string; limit?: number }) {
    try {
      const response = await fetch(`/api/strategies/${strategyId}/signals?limit=${limit}`, {
        headers: {
          'Authorization': `Bearer ${rootState.user.token}`
        }
      })
      const signals = await response.json()
      commit('SET_STRATEGY_SIGNALS', { strategyId, signals })
      return signals
    } catch (error) {
      console.error('获取策略信号失败:', error)
      throw error
    }
  },

  /**
   * 监控策略性能
   */
  startStrategyMonitoring({ commit, state }: any, strategyId: string) {
    const interval = setInterval(async () => {
      if (state.activeStrategies.has(strategyId)) {
        try {
          const response = await fetch(`/api/strategies/${strategyId}/performance`)
          const performance = await response.json()
          commit('UPDATE_STRATEGY_PERFORMANCE', { strategyId, performance })
        } catch (error) {
          console.error('获取策略性能失败:', error)
        }
      }
    }, 5000) // 每5秒更新一次

    return () => clearInterval(interval)
  },

  /**
   * 定期清理旧信号
   */
  startSignalCleanup({ commit }: any) {
    setInterval(() => {
      commit('CLEANUP_OLD_SIGNALS')
    }, 3600000) // 每小时清理一次
  }
}

const getters = {
  /**
   * 获取所有策略
   */
  getAllStrategies: (state: StrategyState) => state.strategies,

  /**
   * 获取运行中的策略
   */
  getActiveStrategies: (state: StrategyState) => {
    return state.strategies.filter(s => state.activeStrategies.has(s.id))
  },

  /**
   * 获取单个策略
   */
  getStrategyById: (state: StrategyState) => (id: string) => {
    return state.strategiesMap.get(id)
  },

  /**
   * 获取策略运行记录
   */
  getStrategyRuns: (state: StrategyState) => (strategyId: string) => {
    return state.strategyRuns.get(strategyId) || []
  },

  /**
   * 获取回测结果
   */
  getBacktestResult: (state: StrategyState) => (strategyId: string) => {
    return state.backtestResults.get(strategyId)
  },

  /**
   * 获取策略信号
   */
  getStrategySignals: (state: StrategyState) => (strategyId: string) => {
    return state.strategySignals.get(strategyId) || []
  },

  /**
   * 获取最新信号
   */
  getLatestSignals: (state: StrategyState) => (limit: number = 10) => {
    const allSignals: TradeSignal[] = []
    for (const signals of state.strategySignals.values()) {
      allSignals.push(...signals.slice(0, 5)) // 每个策略取最新的5个信号
    }

    return allSignals
      .sort((a, b) => new Date(b.signal_time).getTime() - new Date(a.signal_time).getTime())
      .slice(0, limit)
  },

  /**
   * 获取策略性能
   */
  getStrategyPerformance: (state: StrategyState) => (strategyId: string) => {
    return state.strategyPerformance.get(strategyId)
  },

  /**
   * 检查策略是否运行中
   */
  isStrategyRunning: (state: StrategyState) => (strategyId: string) => {
    return state.activeStrategies.has(strategyId)
  }
}

const strategyModule: Module<StrategyState, RootState> = {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
}

export default strategyModule