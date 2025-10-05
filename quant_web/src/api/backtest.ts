import request from '@/utils/request'
import { handleResponse } from '@/utils/responseHandler'
import {
  BacktestTask,
  CreateBacktestTaskRequest,
  BacktestQueryParams,
  BacktestTaskResponse,
  BacktestListResponse,
} from '@/types/api/backtest'
import {BacktestPosition, BacktestTrade, EquityPoint} from "@/types/api";

/**
 * 回测管理API服务
 * 提供回测任务创建、查询、取消、结果获取等功能
 */
export default {
  /**
   * 创建并运行回测任务
   * @param config 回测配置参数
   * @returns 回测任务ID
   */
  async runBacktest(config: CreateBacktestTaskRequest): Promise<{ task_id: string }> {
    return request.post('/backtest/run', config)
      .then(handleResponse)
      .then((data: { task_id: string }) => data)
  },

  /**
   * 获取回测任务列表
   * @param params 查询参数（分页、状态筛选等）
   * @returns 回测任务列表
   */
  async getBacktestTasks(params?: BacktestQueryParams): Promise<BacktestTask[]> {
    return request.get('/backtest/tasks', { params })
      .then(handleResponse)
      .then((data: BacktestListResponse) => data.data.items)
  },

  /**
   * 获取单个回测任务详情
   * @param taskId 回测任务ID
   * @returns 回测任务详情
   */
  async getBacktestTask(taskId: string): Promise<BacktestTask> {
    return request.get(`/backtest/tasks/${taskId}`)
      .then(handleResponse)
      .then((data: BacktestTaskResponse) => data.data)
  },

  /**
   * 取消回测任务
   * @param taskId 回测任务ID
   * @returns 无返回值
   */
  async cancelBacktestTask(taskId: string): Promise<void> {
    return request.delete(`/backtest/tasks/${taskId}`)
      .then(handleResponse)
  },

  /**
   * 获取回测净值曲线数据
   * @param taskId 回测任务ID
   * @returns 净值曲线数据点数组
   */
  async getBacktestEquity(taskId: string): Promise<EquityPoint[]> {
    return request.get(`/backtest/tasks/${taskId}/equity`)
      .then(handleResponse)
      .then((data: { equity: EquityPoint[] }) => data.equity)
  },

  /**
   * 获取回测交易记录
   * @param taskId 回测任务ID
   * @param params 分页参数
   * @returns 交易记录数组
   */
  async getBacktestTrades(taskId: string, params?: {
    skip?: number;
    limit?: number;
  }): Promise<BacktestTrade[]> {
    return request.get(`/backtest/tasks/${taskId}/trades`, { params })
      .then(handleResponse)
      .then((data: { trades: BacktestTrade[] }) => data.trades)
  },

  /**
   * 获取回测持仓快照
   * @param taskId 回测任务ID
   * @param date 指定日期（可选，不指定则返回最新持仓）
   * @returns 持仓快照数组
   */
  async getBacktestPositions(taskId: string, date?: string): Promise<BacktestPosition[]> {
    return request.get(`/backtest/tasks/${taskId}/positions`, {
      params: { date }
    }).then(handleResponse)
      .then((data: { positions: BacktestPosition[] }) => data.positions)
  },

  /**
   * 获取回测绩效报告
   * @param taskId 回测任务ID
   * @returns 详细的绩效报告
   */
  async getBacktestReport(taskId: string): Promise<any> {
    return request.get(`/backtest/tasks/${taskId}/report`)
      .then(handleResponse)
      .then((data: { report: any }) => data.report)
  },

  /**
   * 批量删除回测任务
   * @param taskIds 回测任务ID数组
   * @returns 删除结果
   */
  async deleteBacktestTasks(taskIds: string[]): Promise<{ deleted: number }> {
    return request.delete('/backtest/tasks/batch', {
      data: { task_ids: taskIds }
    }).then(handleResponse)
  },

  /**
   * 复制回测任务
   * @param taskId 原回测任务ID
   * @param newName 新任务名称
   * @returns 新回测任务ID
   */
  async duplicateBacktestTask(taskId: string, newName: string): Promise<{ task_id: string }> {
    return request.post(`/backtest/tasks/${taskId}/duplicate`, {
      new_name: newName
    }).then(handleResponse)
  }
}