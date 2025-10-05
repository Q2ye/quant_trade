// quant_web/src/api/system.ts
import request from '@/utils/request'
import { handleResponse } from '@/utils/responseHandler'
import {
  ApiResponse,
  PaginatedResponse,
  HealthCheckResponse
} from '@/types/api'
import {SystemLog} from "@/types/entities";

/**
 * 系统管理API服务
 * 提供系统状态监控、配置管理、日志查询和系统维护功能
 */

export interface SystemStatus {
  version: string;
  uptime: number;
  status: 'running' | 'stopped' | 'error';
  last_startup: string;
  engine_status: {
    main_engine: string;
    event_engine: string;
    strategy_engine: string;
    data_service: string;
  };
}

export interface SystemSettings {
  data_sync: {
    auto_sync: boolean;
    sync_interval: number;
    data_sources: string[];
  };
  trading: {
    commission_rate: number;
    tax_rate: number;
    min_commission: number;
  };
  risk: {
    max_position_ratio: number;
    max_daily_loss: number;
    enable_auto_stop: boolean;
  };
  notification: {
    enable_email: boolean;
    enable_wechat: boolean;
    risk_notification: boolean;
  };
}

export interface ConnectionStatus {
  database: boolean;
  redis: boolean;
  tushare: boolean;
  broker: boolean;
  last_check: string;
}

export interface ResourceUsage {
  cpu_percent: number;
  memory_percent: number;
  memory_used: number;
  memory_total: number;
  disk_usage: number;
  network_io: {
    bytes_sent: number;
    bytes_recv: number;
  };
}

export interface DatabaseStatus {
  total_tables: number;
  total_records: number;
  stock_data_count: number;
  trade_data_count: number;
  last_optimized: string;
}

export interface SystemLogQueryParams {
  level?: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  module?: string;
  page?: number;
  limit?: number;
  start_time?: string;
  end_time?: string;
}

export default {
  /**
   * 获取系统状态
   * @returns 系统状态信息
   */
  async getSystemStatus(): Promise<SystemStatus> {
    return request.get('/system/status')
      .then(handleResponse)
      .then((data: ApiResponse<SystemStatus>) => data.data)
  },

  /**
   * 获取系统日志
   * @param params 查询参数
   * @returns 系统日志分页结果
   */
  async getSystemLogs(params?: SystemLogQueryParams): Promise<PaginatedResponse<SystemLog>> {
    return request.get('/system/logs', { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<SystemLog>) => data)
  },

  /**
   * 触发数据同步
   * @param params 同步参数
   * @returns 同步任务信息
   */
  async triggerDataSync(params: {
    data_type: string;
    start_date?: string;
    end_date?: string;
    symbols?: string[];
  }): Promise<{ task_id: string }> {
    return request.post('/system/data/sync', params)
      .then(handleResponse)
      .then((data: ApiResponse<{ task_id: string }>) => data.data)
  },

  /**
   * 获取数据同步状态
   * @returns 数据同步状态信息
   */
  async getDataSyncStatus(): Promise<any> {
    return request.get('/system/data/status')
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data)
  },

  /**
   * 获取系统配置
   * @returns 系统配置信息
   */
  async getSystemSettings(): Promise<SystemSettings> {
    return request.get('/system/settings')
      .then(handleResponse)
      .then((data: ApiResponse<SystemSettings>) => data.data)
  },

  /**
   * 更新系统配置
   * @param settings 配置更新参数
   * @returns 更新后的系统配置
   */
  async updateSystemSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
    return request.put('/system/settings', settings)
      .then(handleResponse)
      .then((data: ApiResponse<SystemSettings>) => data.data)
  },

  /**
   * 获取连接状态
   * @returns 各服务连接状态
   */
  async getConnections(): Promise<ConnectionStatus> {
    return request.get('/system/connections')
      .then(handleResponse)
      .then((data: ApiResponse<ConnectionStatus>) => data.data)
  },

  /**
   * 获取资源使用情况
   * @returns 系统资源使用信息
   */
  async getResources(): Promise<ResourceUsage> {
    return request.get('/system/resources')
      .then(handleResponse)
      .then((data: ApiResponse<ResourceUsage>) => data.data)
  },

  /**
   * 获取数据库状态
   * @returns 数据库状态信息
   */
  async getDatabaseStatus(): Promise<DatabaseStatus> {
    return request.get('/system/database')
      .then(handleResponse)
      .then((data: ApiResponse<DatabaseStatus>) => data.data)
  },

  /**
   * 健康检查
   * @returns 健康检查结果
   */
  async healthCheck(): Promise<HealthCheckResponse> {
    return request.get('/system/health')
      .then(handleResponse)
      .then((data: HealthCheckResponse) => data)
  },

  /**
   * 清理系统缓存
   * @returns 清理操作结果
   */
  async clearCache(): Promise<{ cleared: boolean; message: string }> {
    return request.post('/system/cache/clear')
      .then(handleResponse)
      .then((data: ApiResponse<{ cleared: boolean; message: string }>) => data.data)
  },

  /**
   * 重启系统服务
   * @param service 服务名称
   * @returns 重启操作结果
   */
  async restartService(service: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/system/services/${service}/restart`)
      .then(handleResponse)
      .then((data: ApiResponse<{ success: boolean; message: string }>) => data.data)
  }
}