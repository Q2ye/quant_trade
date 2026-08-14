/**
 * 独立场景回测 API（v3.3）
 */
import request from '@/utils/request'

const BASE = '/quantTrade/backtest'

export interface ScenarioRunParams {
  name: string
  code: string
  parameters?: Record<string, any>
  config?: {
    start_date: string
    end_date: string
    initial_capital?: number
    benchmark?: string
    symbols?: string[]
  }
  template_id?: string
  source_strategy_id?: string
}

export interface ScenarioRunResult {
  scenario_id: string
  task_id: string
}

export interface ScenarioPromoteParams {
  scenario_id: string
  strategy_name?: string
}

export interface ScenarioPromoteResult {
  strategy_id: string
}

/** 创建独立场景并启动回测 */
export function runScenario(params: ScenarioRunParams) {
  return request.post<ScenarioRunResult>(`${BASE}/run-scenario`, params)
}

/** 将场景晋升为正式策略 */
export function promoteScenario(params: ScenarioPromoteParams) {
  return request.post<ScenarioPromoteResult>(`${BASE}/promote-scenario`, params)
}
