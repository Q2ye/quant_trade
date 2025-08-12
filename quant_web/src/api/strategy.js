// 策略相关API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 获取策略模板
  getStrategyTemplates() {
    return request.get('/strategy/templates')
      .then(handleResponse)
      .then(data => data.templates)
  },

  // 获取策略列表
  getStrategyList(status = 'all', page = 1, pageSize = 20) {
    return request.get('/strategies', {
      params: { status, page, pageSize }
    })
      .then(handleResponse)
      .then(data => ({
        strategies: data.strategies,
        total: data.total,
        page: data.page
      }))
  },

  // 创建新策略
  createStrategy(strategyData) {
    return request.post('/strategies', strategyData)
      .then(handleResponse)
      .then(data => data.newStrategy)
  },

  // 更新策略
  updateStrategy(id, strategyData) {
    return request.put(`/strategies/${id}`, strategyData)
      .then(handleResponse)
      .then(data => data.updatedStrategy)
  },

  // 删除策略
  deleteStrategy(id) {
    return request.delete(`/strategies/${id}`)
      .then(handleResponse)
  },

  // 获取策略详情
  getStrategyDetails(id) {
    return request.get(`/strategies/${id}`)
      .then(handleResponse)
      .then(data => data.strategy)
  },

  // 启动策略
  startStrategy(id) {
    return request.post(`/strategies/${id}/start`)
      .then(handleResponse)
  },

  // 停止策略
  stopStrategy(id) {
    return request.post(`/strategies/${id}/stop`)
      .then(handleResponse)
  },

  // 获取策略执行日志
  getStrategyLogs(id, limit = 100, level = 'all') {
    return request.get(`/strategies/${id}/logs`, {
      params: { limit, level }
    })
      .then(handleResponse)
      .then(data => data.logs)
  },

  // 获取策略绩效报告
  getStrategyPerformance(id) {
    return request.get(`/strategies/${id}/performance`)
      .then(handleResponse)
      .then(data => data.performance)
  },

  // 克隆策略
  cloneStrategy(id, newName) {
    return request.post(`/strategies/${id}/clone`, { newName })
      .then(handleResponse)
      .then(data => data.newStrategy)
  },

  // 策略参数优化
  optimizeStrategyParams(params) {
    return request.post('/strategy/optimize', params)
      .then(handleResponse)
      .then(data => data.optimizedParams)
  },

  // 策略对比分析
  compareStrategies(strategyIds) {
    return request.post('/strategy/compare', { strategyIds })
      .then(handleResponse)
      .then(data => data.comparison)
  },

  // 获取策略回测配置
  getBacktestConfig(id) {
    return request.get(`/strategies/${id}/backtest-config`)
      .then(handleResponse)
      .then(data => data.config)
  },

  // 运行策略回测
  runStrategyBacktest(id, config) {
    return request.post(`/strategies/${id}/backtest`, config)
      .then(handleResponse)
      .then(data => data.backtestResult)
  },

  // 获取回测结果
  getBacktestResult(backtestId) {
    return request.get(`/backtest/${backtestId}`)
      .then(handleResponse)
      .then(data => data.result)
  },

  // 获取策略持仓
  getStrategyPositions(id) {
    return request.get(`/strategies/${id}/positions`)
      .then(handleResponse)
      .then(data => data.positions)
  },

  // 获取策略信号
  getStrategySignals(id, limit = 100) {
    return request.get(`/strategies/${id}/signals`, {
      params: { limit }
    })
      .then(handleResponse)
      .then(data => data.signals)
  }
}