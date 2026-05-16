// 基础API类型定义

/**
 * 通用API响应格式
 */
export interface ApiResponse<T = any> {
  code: number; // 状态码
  message: string; // 消息
  data: T; // 数据
  timestamp: number; // 时间戳
}

/**
 * 分页响应格式
 */
export interface PaginatedResponse<T = any> extends ApiResponse<{
  items: T[]; // 数据列表
  total: number; // 总条数
  page: number; // 当前页码
  pageSize: number; // 每页大小
  totalPages: number; // 总页数
}> {}

/**
 * 分页查询参数
 */
export interface PaginationParams {
  page?: number; // 页码，从1开始
  pageSize?: number; // 每页大小
  keyword?: string; // 搜索关键词
}

/**
 * 时间范围查询参数
 */
export interface TimeRangeParams {
  startTime?: string; // 开始时间（ISO格式）
  endTime?: string; // 结束时间（ISO格式）
}

/**
 * 排序参数
 */
export interface SortParams {
  sortField?: string; // 排序字段
  sortOrder?: "asc" | "desc"; // 排序方向
}

/**
 * 基础查询参数（组合分页、时间范围、排序）
 */
export interface BaseQueryParams
  extends PaginationParams, TimeRangeParams, SortParams {}

/**
 * ID参数
 */
export interface IdParams {
  id: string; // 资源ID
}

/**
 * 批量操作参数
 */
export interface BatchOperationParams {
  ids: string[]; // 资源ID列表
}

/**
 * 文件上传参数
 */
export interface FileUploadParams {
  file: File; // 文件对象
  category?: string; // 文件分类
  description?: string; // 文件描述
}

/**
 * 系统配置项
 */
export interface SystemConfig {
  key: string; // 配置键
  value: string; // 配置值
  description?: string; // 配置描述
  isPublic?: boolean; // 是否公开
}

/**
 * 字典项接口
 */
export interface DictItem {
  label: string; // 显示标签
  value: string; // 值
  color?: string; // 颜色
  order?: number; // 排序
}

/**
 * 字典响应
 */
export interface DictResponse extends ApiResponse<Record<string, DictItem[]>> {}

/**
 * 系统配置响应
 */
export interface SystemConfigResponse extends ApiResponse<SystemConfig[]> {}

/**
 * 健康检查响应
 */
export interface HealthCheckResponse extends ApiResponse<{
  status: string; // 服务状态
  version: string; // 版本号
  timestamp: number; // 时间戳
  dependencies: {
    // 依赖服务状态
    database: boolean;
    redis: boolean;
    dataSource: boolean;
  };
}> {}
