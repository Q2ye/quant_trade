import request from '@/utils/request'
import { handleResponse } from '@/utils/responseHandler'
import {
  DataSyncRequest,
  DataSyncTask,
  ApiResponse,
  DataSyncResponse as TypesDataSyncResponse
} from '@/types/api'
/**
 * 数据同步API服务
 * 提供股票数据、财务数据等各类金融数据的同步功能
 */
export interface SyncStatusResponse {
  is_running: boolean;
  last_run?: string;
  progress: number;
  current_task?: string;
  results?: any;
  error?: string;
  estimated_remaining?: number;
}

export default {
  /**
   * 获取数据同步状态
   * @returns 同步状态信息
   */
  async getSyncStatus(): Promise<SyncStatusResponse> {
    return request.get('/data-sync/status')
      .then(handleResponse)
      .then((data: SyncStatusResponse) => data)
  },

  /**
   * 获取支持的数据类型列表
   * @returns 支持的数据类型数组
   */
  async getSupportedDataTypes(): Promise<string[]> {
    return request.get('/data-sync/supported-data-types')
      .then(handleResponse)
      .then((data: { types: string[] }) => data.types)
  },

  /**
   * 同步股票基本信息
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncStockBasic(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/stock-basic', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步日线数据
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncDailyData(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/daily', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步周线数据
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncWeeklyData(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/weekly', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步月线数据
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncMonthlyData(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/monthly', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步资金流向数据
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncMoneyflowData(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/moneyflow', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步交易日历
   * @param params 交易日历参数
   * @returns 同步任务响应
   */
  async syncTradeCalendar(params?: {
    exchanges?: string[];
    start_date?: string;
    end_date?: string;
  }): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/trade-calendar', null, { params })
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 同步所有数据
   * @param syncData 同步参数
   * @returns 同步任务响应
   */
  async syncAllData(syncData: DataSyncRequest): Promise<TypesDataSyncResponse> {
    return request.post('/data-sync/all', syncData)
      .then(handleResponse)
      .then((data: TypesDataSyncResponse) => data)
  },

  /**
   * 取消数据同步任务
   * @returns 取消操作结果
   */
  async cancelSync(): Promise<void> {
    return request.post('/data-sync/cancel')
      .then(handleResponse)
  }
}