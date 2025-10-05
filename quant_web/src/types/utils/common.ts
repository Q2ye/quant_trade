// 通用工具类型

/**
 * 可空类型：T | null
 */
export type Nullable<T> = T | null;

/**
 * 可选类型：T | undefined
 */
export type Optional<T> = T | undefined;

/**
 * 字典类型：Record<string, T>
 */
export type Dictionary<T> = Record<string, T>;

/**
 * 主题类型：亮色/暗色
 */
export type Theme = 'light' | 'dark';

/**
 * 语言类型：中文/英文
 */
export type Language = 'zh-CN' | 'en-US';

/**
 * 排序参数接口
 */
export interface SortParams {
  field: string;           // 排序字段
  order: 'asc' | 'desc';   // 排序方向：升序/降序
}

/**
 * 过滤参数接口
 */
export interface FilterParams {
  [key: string]: any;      // 动态过滤条件
}

/**
 * 分页参数接口
 */
export interface PaginationParams {
  page: number;            // 当前页码
  pageSize: number;        // 每页大小
  total?: number;          // 总数（可选）
}

/**
 * 分页响应接口
 */
export interface PaginationResponse<T> {
  data: T[];               // 数据列表
  total: number;           // 总数
  page: number;            // 当前页
  pageSize: number;        // 每页大小
  totalPages: number;      // 总页数
}

/**
 * API响应基础接口
 */
export interface ApiResponse<T = any> {
  code: number;            // 状态码
  message: string;         // 消息
  data: T;                 // 数据
  success: boolean;        // 是否成功
}

/**
 * 日期范围接口
 */
export interface DateRange {
  startDate: string;       // 开始日期
  endDate: string;         // 结束日期
}

/**
 * 键值对接口
 */
export interface KeyValuePair<K = string, V = any> {
  key: K;                  // 键
  value: V;                // 值
  label?: string;          // 显示标签（可选）
}