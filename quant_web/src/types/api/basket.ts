// quant_web/src/types/api/basket.ts
// 响应类型定义
import { ApiResponse } from "@/types";
import { PaginatedResponse } from "@/types/api/base";
import {
  Basket,
  BasketPerformance,
  BasketStatistics,
  BacktestResult
} from "@/types/entities/basket";

export interface BasketResponse extends ApiResponse<Basket> {}
export interface BasketListResponse extends PaginatedResponse<Basket> {}
export interface BasketPerformanceResponse extends ApiResponse<BasketPerformance> {}
export interface BasketStatisticsResponse extends ApiResponse<BasketStatistics> {}
export interface BasketBacktestResponse extends ApiResponse<BacktestResult> {}