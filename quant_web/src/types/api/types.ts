// quant_web/src/types/api/types.ts
// 通用API类型定义（兼容旧版本）
import { ApiResponse as NewApiResponse, PaginatedResponse as NewPaginatedResponse } from './response';

/**
 * @deprecated 请使用从 './response' 导入的 ApiResponse
 */
export interface ApiResponse<T = any> extends NewApiResponse<T> {}

/**
 * @deprecated 请使用从 './response' 导入的 PaginatedResponse
 */
export interface PaginatedResponse<T> extends NewPaginatedResponse<T> {}
