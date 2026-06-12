// quant_web/src/api/market.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  PaginatedResponse,
  StockQueryParams,
  QuoteQueryParams,
  KLineData,
  IndexInfo,
  SectorInfo,
} from "@/types";
import { FinancialData, StockBasic } from "@/types";
import type { DashboardOverview, StockFullResponse } from "@/types/entities/market";
import type { ScreenerParams, ScreenerResult, IndustryNode, IndustryDetail, IndustryHeatmapItem } from "@/types/entities/market";

export interface StockListResult {
  stocks: StockBasic[];
  total: number;
  page: number;
}

export default {
  async getStocks(params?: StockQueryParams): Promise<PaginatedResponse<StockBasic>> {
    return request.get("/quantTrade/data/stocks", { params }).then(handleResponse).then((data: PaginatedResponse<StockBasic>) => data);
  },
  async getStockDetail(code: string): Promise<StockBasic> {
    return request.get(`/quantTrade/data/stocks/${code}`).then(handleResponse).then((data: { stock: StockBasic }) => data.stock);
  },
  async getStockHistory(code: string, params: QuoteQueryParams): Promise<KLineData[]> {
    return request.get(`/quantTrade/data/stocks/${code}/history`, { params }).then(handleResponse).then((data: { historical: KLineData[] }) => data.historical);
  },
  async getETFs(params?: { page?: number; limit?: number }): Promise<StockBasic[]> {
    return request.get("/quantTrade/data/etfs", { params }).then(handleResponse).then((data: { etfs: StockBasic[] }) => data.etfs);
  },
  async getETFDetail(code: string): Promise<StockBasic> {
    return request.get(`/quantTrade/data/etfs/${code}`).then(handleResponse).then((data: { etf: StockBasic }) => data.etf);
  },
  async getIndexes(): Promise<IndexInfo[]> {
    return request.get("/quantTrade/data/indexes").then(handleResponse).then((data: { indexes: IndexInfo[] }) => data.indexes);
  },
  async getIndexDetail(code: string): Promise<IndexInfo> {
    return request.get(`/quantTrade/data/indexes/${code}`).then(handleResponse).then((data: { index: IndexInfo }) => data.index);
  },
  async getSectors(): Promise<SectorInfo[]> {
    return request.get("/quantTrade/data/sectors").then(handleResponse).then((data: { sectors: SectorInfo[] }) => data.sectors);
  },
  async getFinancialData(code: string, params: { reportDate?: string }): Promise<FinancialData[]> {
    return request.get(`/quantTrade/data/stocks/${code}/financial`, { params }).then(handleResponse).then((data: { financial: FinancialData[] }) => data.financial);
  },

  // ---- Phase 1: Dashboard + StockDetail ----
  async getDashboardOverview(): Promise<DashboardOverview> {
    return request.get("/quantTrade/market/dashboard/overview").then(handleResponse).then((data: any) => data.data);
  },
  async getStockFull(ts_code: string): Promise<StockFullResponse | null> {
    return request.get(`/quantTrade/market/stocks/${ts_code}/full`).then(handleResponse).then((data: any) => data.data);
  },

  // ---- Phase 2: Screener + Industry ----
  async getScreener(params: ScreenerParams): Promise<ScreenerResult> {
    return request.post("/quantTrade/market/screener", params).then(handleResponse).then((d: any) => d.data);
  },
  async getIndustryTree(): Promise<IndustryNode[]> {
    return request.get("/quantTrade/market/industries").then(handleResponse).then((d: any) => d.data);
  },
  async getIndustryDetail(code: string): Promise<IndustryDetail> {
    return request.get(`/quantTrade/market/industries/${code}`).then(handleResponse).then((d: any) => d.data);
  },
  async getIndustryHeatmap(): Promise<IndustryHeatmapItem[]> {
    return request.get("/quantTrade/market/industries/heatmap").then(handleResponse).then((d: any) => d.data);
  },

  // ---- Phase 3: Financial + MoneyFlow ----
  async getFinancialCompare(params: { codes: string[]; metrics?: string[]; end_date?: string }): Promise<any[]> {
    return request.post("/quantTrade/market/financial/indicators", params).then(handleResponse).then((d: any) => d.data);
  },
  async getFinancialStatements(code: string, type: string, limit?: number): Promise<any[]> {
    return request.get(`/quantTrade/market/stocks/${code}/financial/statements`, { params: { type, limit } }).then(handleResponse).then((d: any) => d.data);
  },
  async getTopMoneyflow(direction?: string, limit?: number): Promise<any[]> {
    return request.get("/quantTrade/market/moneyflow/top", { params: { direction, limit } }).then(handleResponse).then((d: any) => d.data);
  },
  async getHsgtHistory(days?: number): Promise<any[]> {
    return request.get("/quantTrade/market/moneyflow/hsgt", { params: { days } }).then(handleResponse).then((d: any) => d.data);
  },
  async getStockMoneyflow(code: string, days?: number): Promise<any[]> {
    return request.get(`/quantTrade/market/stocks/${code}/moneyflow`, { params: { days } }).then(handleResponse).then((d: any) => d.data);
  },

  // ---- Phase 4: ETF/Index enhanced ----
  async getEtfShares(code: string, limit?: number): Promise<any[]> {
    return request.get(`/quantTrade/market/etfs/${code}/shares`, { params: { limit } }).then(handleResponse).then((d: any) => d.data);
  },
  async getEtfBenchmark(code: string): Promise<any> {
    return request.get(`/quantTrade/market/etfs/${code}/benchmark`).then(handleResponse).then((d: any) => d.data);
  },
  async getIndexWeights(code: string): Promise<any[]> {
    return request.get(`/quantTrade/market/indexes/${code}/weights`).then(handleResponse).then((d: any) => d.data);
  },
  async getIndexValuation(code: string, limit?: number): Promise<any[]> {
    return request.get(`/quantTrade/market/indexes/${code}/valuation`, { params: { limit } }).then(handleResponse).then((d: any) => d.data);
  },
  async getIndexHistory(code: string, limit?: number): Promise<any[]> {
    return request.get(`/quantTrade/market/indexes/${code}/history`, { params: { limit } }).then(handleResponse).then((d: any) => d.data);
  },
};
