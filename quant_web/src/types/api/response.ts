// 统一响应类型定义

/**
 * 基础API响应接口
 * @template T 数据类型
 */
export interface ApiResponse<T = any> {
  code: number;           // 状态码：0-成功，非0-失败
  message: string;        // 响应消息
  data: T;               // 响应数据
  timestamp: number;     // 时间戳
}

/**
 * 分页响应接口
 * @template T 列表项数据类型
 */
export interface PaginatedResponse<T> extends ApiResponse<{
  items: T[];           // 数据列表
  total: number;        // 总记录数
  page: number;         // 当前页码
  pageSize: number;     // 每页大小
}> {}


/**
 * WebSocket消息接口
 * @template T 消息数据类型
 */
export interface WebSocketMessage<T = any> {
  type: string;         // 消息类型
  data: T;              // 消息数据
  timestamp: number;    // 时间戳
}

/**
 * 文件上传响应接口
 */
export interface FileUploadResponse extends ApiResponse<{
  fileId: string;       // 文件ID
  fileName: string;     // 文件名
  fileUrl: string;      // 文件访问URL
  fileSize: number;     // 文件大小
}> {}

/**
 * 批量操作响应接口
 */
export interface BatchOperationResponse extends ApiResponse<{
  success: number;      // 成功数量
  failed: number;       // 失败数量
  errors: Array<{       // 错误详情
    id: string;         // 操作项ID
    message: string;    // 错误信息
  }>;
}> {}