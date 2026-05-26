// quant_web/src/types/api/basket.ts
// 响应类型定义
import { ApiResponse } from "./common";
import { PaginatedResponse } from "./common";
import {
  Basket,
  BasketPerformance,
  BasketStatistics,
  BacktestResult,
} from "./entities-basket";

export interface BasketResponse extends ApiResponse<Basket> {}
export interface BasketListResponse extends PaginatedResponse<Basket> {}
export interface BasketPerformanceResponse extends ApiResponse<BasketPerformance> {}
export interface BasketStatisticsResponse extends ApiResponse<BasketStatistics> {}
export interface BasketBacktestResponse extends ApiResponse<BacktestResult> {}
