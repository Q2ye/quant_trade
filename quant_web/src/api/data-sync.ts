// quant_web/src/api/events-sync.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";

/**
 * 数据同步API服务 - 基于后端批量数据同步设计实现
 * 支持多数据类型批量同步和实时状态监控
 */

// 后端返回的同步进度子对象
export interface SyncProgress {
  total_tasks: number;
  completed_tasks: number;
  current_task?: string;
  progress_percentage: number;
  estimated_time_remaining?: number;
}

// 同步状态响应接口 - 与后端SyncStatusResponse完全匹配
export interface SyncStatusResponse {
  success: boolean;
  task_id: string;
  status: string;              // pending | running | completed | failed | cancelled
  progress: SyncProgress;
  results?: SyncResultItem[];
  created_by: string;
  created_at: string;
  updated_at: string;
  message?: string;
}

// 同步结果项
export interface SyncResultItem {
  data_type: string;
  success: boolean;
  records_added: number;
  records_updated: number;
  records_failed: number;
  start_time: string;
  end_time: string;
  message?: string;
}

// 同步任务项 — 与后端 SyncTaskItem 完全匹配
export interface SyncTaskItem {
  data_type: string;         // 数据类型代码，如 stock_list, daily_quotes
  start_date?: string;       // 开始日期 YYYY-MM-DD
  end_date?: string;         // 结束日期 YYYY-MM-DD
  force_update?: boolean;    // 是否强制全量更新
}

// 批量同步请求接口 — 与后端 BatchSyncRequest 完全匹配
export interface BatchSyncRequest {
  tasks: SyncTaskItem[];                          // 同步任务列表（必填，至少1项）
  priority?: "low" | "medium" | "high" | "critical"; // 优先级，默认 medium
  notify_on_complete?: boolean;                   // 完成后是否通知，默认 true
  callback_url?: string;                          // 完成回调 URL
}

// 前端使用的简化参数（向后兼容层会转换为 BatchSyncRequest）
export interface SyncRequest {
  data_types?: string[];      // 数据类型代码数组（可选，为空时使用核心类型）
  start_date?: string;
  end_date?: string;
  days?: number;              // 从今天往前推算天数（与 start_date 互斥）
  stock_codes?: string[];     // 股票代码过滤
  exchange?: string;          // 交易所过滤
  batch_size?: number;        // 批次大小
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
  is_core: boolean;
}

// 同步任务历史记录
export interface SyncTaskRecord {
  id: string;
  task_id: string;
  task_type: string;
  data_types?: string[];
  status: string;
  start_time?: string;
  end_time?: string;
  records_processed: number;
  records_succeeded: number;
  records_failed: number;
  total_records: number;
  parameters?: Record<string, any>;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
}

// 数据质量相关接口
export interface QualityMetric {
  metric_name: string;
  metric_value: number;
  threshold?: number;
  status: string;
}

export interface DataIssue {
  issue_type: string;
  severity: string;
  count: number;
  description: string;
  affected_records?: string[];
}

export interface DataQualityResponse {
  success: boolean;
  data_type?: string;
  date_range?: { start: string; end: string };
  quality_score: number;
  quality_level: string;
  metrics: QualityMetric[];
  issues: DataIssue[];
  recommendations: string[];
  generated_at: string;
  message?: string;
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
  async getSyncStatus(taskId?: string): Promise<SyncStatusResponse> {
    const params = taskId ? { task_id: taskId } : {};
    return request
      .get(`${this.baseUrl}/status`, { params })
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
      .post(`${this.baseUrl}/batch`, requestData)
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
      .post(`${this.baseUrl}/quick`)
      .then(handleResponse)
      .then((data: SyncResponse) => data)
      .catch((error) => {
        console.error("快速同步请求失败:", error);
        throw error;
      });
  }

  /**
   * 将简化参数转为后端 BatchSyncRequest 格式
   */
  private _toBatchRequest(
    dataType: string,
    params: { start_date?: string; end_date?: string; days?: number },
  ): BatchSyncRequest {
    const task: SyncTaskItem = { data_type: dataType };
    if (params.start_date) {
      task.start_date = params.start_date;
    } else if (params.days) {
      const d = new Date();
      d.setDate(d.getDate() - params.days);
      task.start_date = d.toISOString().slice(0, 10);
    }
    if (params.end_date) task.end_date = params.end_date;
    return { tasks: [task], priority: "medium" };
  }

  /**
   * 全量同步 - 同步所有数据类型
   * @param requestData 同步参数
   * @returns 同步任务响应
   */
  async fullSyncData(requestData: SyncRequest = {}): Promise<SyncResponse> {
    const types = requestData.data_types && requestData.data_types.length > 0
      ? requestData.data_types
      : ["stock_list", "daily_quotes", "trade_calendar"];
    const tasks: SyncTaskItem[] = types.map((dt) => {
      const item: SyncTaskItem = { data_type: dt };
      if (requestData.start_date) item.start_date = requestData.start_date;
      else if (requestData.days) {
        const d = new Date();
        d.setDate(d.getDate() - requestData.days);
        item.start_date = d.toISOString().slice(0, 10);
      }
      if (requestData.end_date) item.end_date = requestData.end_date;
      return item;
    });
    return this.batchSyncData({ tasks, priority: "medium" });
  }

  /**
   * 获取同步任务历史列表
   */
  async getSyncTasks(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; tasks: SyncTaskRecord[]; total: number }> {
    return request
      .get(`${this.baseUrl}/tasks`, { params })
      .then(handleResponse);
  }

  /**
   * 获取数据质量报告
   * @returns 数据质量报告
   */
  async getDataQuality(check = false): Promise<DataQualityResponse> {
    return request
      .get("/quantTrade/data/quality", { params: { check } })
      .then(handleResponse)
      .then((data: DataQualityResponse) => data)
      .catch((error) => {
        console.error("获取数据质量报告失败:", error);
        throw error;
      });
  }

  /** 执行数据质量检查（force check） */
  async runQualityCheck(): Promise<DataQualityResponse> {
    return this.getDataQuality(true);
  }

  /** 删除质量检查记录 */
  async deleteQualityRecords(data_type?: string): Promise<{ deleted: number }> {
    return request
      .delete("/quantTrade/data/quality", { params: { data_type } })
      .then(handleResponse);
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
   * 删除同步任务记录
   * @param taskId 任务ID
   */
  async deleteSyncTask(taskId: string): Promise<{ task_id: string; deleted: boolean }> {
    return request
      .delete(`${this.baseUrl}/tasks/${taskId}`)
      .then(handleResponse)
      .catch((error) => {
        console.error("删除同步任务失败:", error);
        throw error;
      });
  }

  /** 批量删除同步任务 */
  async batchDeleteSyncTasks(taskIds: string[]): Promise<{ deleted: string[]; failed: Array<{ task_id: string; reason: string }>; total: number }> {
    return request
      .delete(`${this.baseUrl}/tasks/batch`, { data: taskIds })
      .then(handleResponse)
      .catch((error) => {
        console.error("批量删除同步任务失败:", error);
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
    return this.batchSyncData(this._toBatchRequest("stock_list", params));
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
    return this.batchSyncData(this._toBatchRequest("daily_quotes", params));
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
    return this.batchSyncData(this._toBatchRequest("weekly_quotes", params));
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
    return this.batchSyncData(this._toBatchRequest("monthly_quotes", params));
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
    return this.batchSyncData(this._toBatchRequest("moneyflow", params));
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
