// 仪表盘 API 响应类型
import { ApiResponse } from "./common";
import { DashboardOverview, MarketStatus } from "./entities-dashboard";

export interface DashboardOverviewResponse extends ApiResponse<DashboardOverview> {}
export interface MarketStatusResponse extends ApiResponse<MarketStatus> {}
