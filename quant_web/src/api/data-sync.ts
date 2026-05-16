// quant_web/src/api/events-sync.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

/**
 * 数据同步API服务 - 基于后端批量数据同步设计实现
 * 支持多数据类型批量同步和实时状态监控
 */

// 同步状态响应接口 - 与后端SyncStatusResponse完全匹配
export interface SyncStatusResponse {
  is_running: boolean;
  last_run?: string;
  progress: number;
  current_task?: string;
  results?: Record<string, any>;
  error?: string;
  estimated_remaining?: number;
  total_tasks: number;
  completed_tasks: number;
  elapsed_time?: number;
  start_time?: string;
  task_id?: string;
  task_queue?: string[];
}

// 批量同步请求接口 - 与后端BatchSyncRequest完全匹配
export interface BatchSyncRequest {
  data_types: string[];
  days?: number;
  start_date?: string;
  end_date?: string;
  stock_codes?: string[];
  exchange?: string;
  batch_size?: number;
  sync_mode?: string;
}

// 基础同步请求接口 - 与后端SyncRequest完全匹配
export interface SyncRequest {
  days?: number;
  start_date?: string;
  end_date?: string;
  stock_codes?: string[];
  exchange?: string;
  batch_size?: number;
}

// 同步响应接口 - 与后端SyncResponse完全匹配
export interface SyncResponse {
  status: string;
  message: string;
  task_id?: string;
  estimated_time?: number;
  total_tasks?: number;
  current_progress?: number;
  sync_mode?: string;
}

// 数据类型信息接口 - 与后端DataTypeInfo完全匹配
export interface DataTypeInfo {
  code: string;
  name: string;
  description: string;
  estimated_time: number;
}

/**
 * 数据同步API服务类
 * 完全适配后端数据同步接口设计
 */
class DataSyncService {
  private readonly baseUrl = "/quantTrade/data/sync";

  /**
   * 获取数据同步状态
   * @returns 同步状态信息
   */
  async getSyncStatus(): Promise<SyncStatusResponse> {
    return request
      .get(`${this.baseUrl}/status`)
      .then(handleResponse)
      .then((data: SyncStatusResponse) => data)
      .catch((error) => {
        console.error("获取同步状态失败:", error);
        throw error;
      });
  }

  /**
   * 获取支持的数据类型列表及详细信息
   * @returns 数据类型信息数组
   */
  async getSupportedDataTypes(): Promise<DataTypeInfo[]> {
    return request
      .get(`${this.baseUrl}/supported-data-types`)
      .then(handleResponse)
      .then((data: DataTypeInfo[]) => data)
      .catch((error) => {
        console.error("获取数据类型列表失败:", error);
        throw error;
      });
  }

  /**
   * 批量同步数据 - 核心接口
   * @param requestData 批量同步请求参数
   * @returns 同步任务响应
   */
  async batchSyncData(requestData: BatchSyncRequest): Promise<SyncResponse> {
    return request
      .post(`${this.baseUrl}/batch-sync`, requestData)
      .then(handleResponse)
      .then((data: SyncResponse) => data)
      .catch((error) => {
        console.error("批量同步请求失败:", error);
        throw error;
      });
  }

  /**
   * 快速同步 - 同步核心数据类型
   * @returns 同步任务响应
   */
  async quickSyncData(): Promise<SyncResponse> {
    return request
      .post(`${this.baseUrl}/quick-sync`)
      .then(handleResponse)
      .then((data: SyncResponse) => data)
      .catch((error) => {
        console.error("快速同步请求失败:", error);
        throw error;
      });
  }

  /**
   * 全量同步 - 同步所有数据类型
   * @param requestData 同步参数
   * @returns 同步任务响应
   */
  async fullSyncData(requestData: SyncRequest = {}): Promise<SyncResponse> {
    return request
      .post(`${this.baseUrl}/full-sync`, requestData)
      .then(handleResponse)
      .then((data: SyncResponse) => data)
      .catch((error) => {
        console.error("全量同步请求失败:", error);
        throw error;
      });
  }

  /**
   * 取消当前同步任务
   * @returns 取消操作结果
   */
  async cancelSync(): Promise<void> {
    return request
      .post(`${this.baseUrl}/cancel`)
      .then(handleResponse)
      .catch((error) => {
        console.error("取消同步任务失败:", error);
        throw error;
      });
  }

  /**
   * 同步股票基本信息（向后兼容）
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncStockBasic(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    const requestData: BatchSyncRequest = {
      data_types: ["stock_basic"],
      ...params,
    };
    return this.batchSyncData(requestData);
  }

  /**
   * 同步日线数据（向后兼容）
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncDailyData(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    const requestData: BatchSyncRequest = {
      data_types: ["daily"],
      ...params,
    };
    return this.batchSyncData(requestData);
  }

  /**
   * 同步周线数据（向后兼容）
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncWeeklyData(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    const requestData: BatchSyncRequest = {
      data_types: ["weekly"],
      ...params,
    };
    return this.batchSyncData(requestData);
  }

  /**
   * 同步月线数据（向后兼容）
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncMonthlyData(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    const requestData: BatchSyncRequest = {
      data_types: ["monthly"],
      ...params,
    };
    return this.batchSyncData(requestData);
  }

  /**
   * 同步资金流向数据（向后兼容）
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncMoneyflowData(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    const requestData: BatchSyncRequest = {
      data_types: ["moneyflow"],
      ...params,
    };
    return this.batchSyncData(requestData);
  }

  /**
   * 同步所有数据类型（全量同步）- 向后兼容
   * @param params 同步参数
   * @returns 同步任务响应
   */
  async syncAllData(
    params: {
      days?: number;
      start_date?: string;
      end_date?: string;
      stock_codes?: string[];
      exchange?: string;
      batch_size?: number;
    } = {},
  ): Promise<SyncResponse> {
    return this.fullSyncData(params);
  }
}

// 创建单例实例
export const dataSyncService = new DataSyncService();

export default dataSyncService;
