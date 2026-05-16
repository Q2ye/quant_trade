// quant_web/src/types/api/events.ts
// 系统管理API类型定义
import { ApiResponse } from "@/types";
import { PaginatedResponse, PaginationParams, TimeRangeParams } from "./base";
import {
  SystemLog,
  SystemMetrics,
  ScheduledTask,
  SystemSetting,
  DataSourceStatus,
  SystemBackupRequest,
  SystemBackup,
} from "@/types/entities/system";

/**
 * 系统日志查询参数
 */
export interface SystemLogQueryParams
  extends PaginationParams, TimeRangeParams {
  level?: "info" | "warn" | "error" | "debug"; // 日志级别
  module?: string; // 模块名称
  user_id?: string; // 用户ID
}

/**
 * 系统配置更新参数
 */
export interface SystemConfigUpdate {
  key: string; // 配置键
  value: string; // 配置值
}

// 响应类型定义
export interface SystemLogsResponse extends PaginatedResponse<SystemLog> {}
export interface SystemMetricsResponse extends ApiResponse<SystemMetrics> {}
export interface ScheduledTasksResponse extends ApiResponse<ScheduledTask[]> {}
export interface SystemConfigResponse extends ApiResponse<SystemSetting[]> {}
export interface DataSourceStatusResponse extends ApiResponse<
  DataSourceStatus[]
> {}
export interface SystemBackupResponse extends ApiResponse<SystemBackup> {}
export interface SystemBackupListResponse extends PaginatedResponse<SystemBackup> {}
export interface SystemHealthResponse extends ApiResponse<{
  status: "healthy" | "degraded" | "unhealthy";
  components: {
    database: boolean;
    redis: boolean;
    dataSources: Record<string, boolean>;
    api: boolean;
  };
}> {}
