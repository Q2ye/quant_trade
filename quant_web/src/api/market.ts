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
import type {
  DashboardOverview,
  StockFullResponse,
  KLineItem,
} from "@/types/entities/market";
import type {
  ScreenerParams,
  ScreenerResult,
  IndustryNode,
  IndustryDetail,
  IndustryHeatmapItem,
} from "@/types/entities/market";

export interface StockListResult {
  stocks: StockBasic[];
  total: number;
  page: number;
}

export default {
  async getStocks(
    params?: StockQueryParams,
  ): Promise<PaginatedResponse<StockBasic>> {
    return request
      .get("/quantTrade/data/stocks", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<StockBasic>) => data);
  },
  async getStockDetail(code: string): Promise<StockBasic> {
    return request
      .get(`/quantTrade/data/stocks/${code}`)
      .then(handleResponse)
      .then((data: { stock: StockBasic }) => data.stock);
  },
  async getStockHistory(
    code: string,
    params: QuoteQueryParams,
  ): Promise<KLineData[]> {
    return request
      .get(`/quantTrade/data/stocks/${code}/history`, { params })
      .then(handleResponse)
      .then((data: { historical: KLineData[] }) => data.historical);
  },
  async getETFs(params?: {
    page?: number;
    limit?: number;
  }): Promise<{ etfs: any[]; total: number; page: number }> {
    return request
      .get("/quantTrade/data/etfs", { params })
      .then(handleResponse)
      .then((d: any) => d);
  },
  async getETFDetail(code: string): Promise<StockBasic> {
    return request
      .get(`/quantTrade/data/etfs/${code}`)
      .then(handleResponse)
      .then((data: { etf: StockBasic }) => data.etf);
  },
  async getIndexes(): Promise<IndexInfo[]> {
    return request
      .get("/quantTrade/data/indexes")
      .then(handleResponse)
      .then((data: { indexes: IndexInfo[] }) => data.indexes);
  },
  async getIndexDetail(code: string): Promise<IndexInfo> {
    return request
      .get(`/quantTrade/data/indexes/${code}`)
      .then(handleResponse)
      .then((data: { index: IndexInfo }) => data.index);
  },
  async getSectors(): Promise<SectorInfo[]> {
    return request
      .get("/quantTrade/data/sectors")
      .then(handleResponse)
      .then((data: { sectors: SectorInfo[] }) => data.sectors);
  },
  async getFinancialData(
    code: string,
    params: { reportDate?: string },
  ): Promise<FinancialData[]> {
    return request
      .get(`/quantTrade/data/stocks/${code}/financial`, { params })
      .then(handleResponse)
      .then((data: { financial: FinancialData[] }) => data.financial);
  },

  // ---- Phase 1: Dashboard + StockDetail ----
  async getDashboardOverview(): Promise<DashboardOverview> {
    return request
      .get("/quantTrade/market/dashboard/overview")
      .then(handleResponse)
      .then((data: any) => data.data);
  },
  async getStockFull(ts_code: string): Promise<StockFullResponse | null> {
    return request
      .get(`/quantTrade/market/stocks/${ts_code}/full`)
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  /** 按日期范围获取 K 线 — 用于图表动态加载更早的历史数据 */
  async getStockKline(
    ts_code: string,
    period: "daily" | "weekly" | "monthly" | "moneyflow" = "daily",
    beforeDate?: string,
    limit: number = 500,
  ): Promise<KLineItem[]> {
    return request
      .get(`/quantTrade/market/stocks/${ts_code}/kline`, {
        params: { period, before_date: beforeDate, limit },
      })
      .then(handleResponse)
      .then((data: any) => data.data);
  },

  // ---- Phase 2: Screener + Industry ----
  async getScreener(params: ScreenerParams): Promise<ScreenerResult> {
    return request
      .post("/quantTrade/market/screener", params)
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndustryTree(): Promise<IndustryNode[]> {
    return request
      .get("/quantTrade/market/industries")
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndustryDetail(code: string): Promise<IndustryDetail> {
    return request
      .get(`/quantTrade/market/industries/${code}`)
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndustryHeatmap(params?: {
    windows?: string;
  }): Promise<IndustryHeatmapItem[]> {
    return request
      .get("/quantTrade/market/industries/heatmap", { params })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndustryHistory(code: string, limit?: number): Promise<any[]> {
    return request
      .get(`/quantTrade/market/industries/${code}/history`, {
        params: { limit },
      })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndustryTrend(days?: number): Promise<IndustryTrendResponse> {
    return request
      .get("/quantTrade/market/industries/trend", { params: { days } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },

  // ---- Phase 3: Financial + MoneyFlow ----
  async getFinancialCompare(params: {
    codes: string[];
    metrics?: string[];
    end_date?: string;
  }): Promise<any[]> {
    return request
      .post("/quantTrade/market/financial/indicators", params)
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getFinancialStatements(
    code: string,
    type: string,
    limit?: number,
  ): Promise<any[]> {
    return request
      .get(`/quantTrade/market/stocks/${code}/financial/statements`, {
        params: { type, limit },
      })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getTopMoneyflow(direction?: string, limit?: number): Promise<any[]> {
    return request
      .get("/quantTrade/market/moneyflow/top", { params: { direction, limit } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getHsgtHistory(days?: number): Promise<any[]> {
    return request
      .get("/quantTrade/market/moneyflow/hsgt", { params: { days } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getStockMoneyflow(code: string, days?: number): Promise<any[]> {
    return request
      .get(`/quantTrade/market/stocks/${code}/moneyflow`, { params: { days } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },

  // ---- Phase 4: ETF/Index enhanced ----
  async getEtfShares(code: string, limit?: number): Promise<any[]> {
    return request
      .get(`/quantTrade/market/etfs/${code}/shares`, { params: { limit } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getEtfBenchmark(code: string): Promise<any> {
    return request
      .get(`/quantTrade/market/etfs/${code}/benchmark`)
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndexWeights(
    code: string,
    offset?: number,
    limit?: number,
  ): Promise<{ total: number; items: any[] }> {
    return request
      .get(`/quantTrade/market/indexes/${code}/weights`, {
        params: { offset: offset ?? 0, limit: limit ?? 50 },
      })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndexValuation(code: string, limit?: number): Promise<any[]> {
    return request
      .get(`/quantTrade/market/indexes/${code}/valuation`, {
        params: { limit },
      })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndexHistory(code: string, limit?: number): Promise<any[]> {
    return request
      .get(`/quantTrade/market/indexes/${code}/history`, { params: { limit } })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
  async getIndexSectorExposure(code: string): Promise<any[]> {
    return request
      .get(`/quantTrade/market/indexes/${code}/sector-exposure`)
      .then(handleResponse)
      .then((d: any) => d.data);
  },

  // ---- Phase 5: Sector MoneyFlow ----
  async getSectorMoneyflow(): Promise<any[]> {
    return request
      .get("/quantTrade/market/moneyflow/sector")
      .then(handleResponse)
      .then((d: any) => d.data);
  },

  // ---- Phase 6: Signals + Factor Scores + Style Factors ----
  async getStockSignals(
    code: string,
    recent?: number,
  ): Promise<SignalMarker[]> {
    return request
      .get(`/quantTrade/market/stocks/${code}/signals`, {
        params: { recent: recent ?? 20 },
      })
      .then(handleResponse)
      .then((d: any) => d.data || [])
      .catch(() => []);
  },
  async getStockFactorScores(
    code: string,
  ): Promise<Record<string, { value: number; percentile: number }> | null> {
    return request
      .get(`/quantTrade/market/stocks/${code}/factor-scores`)
      .then(handleResponse)
      .then((d: any) => d.data)
      .catch(() => null);
  },
  async getStyleFactors(): Promise<any[]> {
    return request
      .get("/quantTrade/market/dashboard/style-factors")
      .then(handleResponse)
      .then((d: any) => d.data || [])
      .catch(() => []);
  },
  async getSectorTurnover(): Promise<{ turnover_rate: number } | null> {
    return request
      .get("/quantTrade/market/dashboard/sector-turnover")
      .then(handleResponse)
      .then((d: any) => d.data || null)
      .catch(() => null);
  },
  async getWatchlist(): Promise<any[]> {
    return request
      .get("/quantTrade/market/user/watchlist")
      .then(handleResponse)
      .then((d: any) => d.data || [])
      .catch(() => []);
  },
  async saveWatchlist(codes: string[]): Promise<boolean> {
    return request
      .put("/quantTrade/market/user/watchlist", { codes })
      .then(handleResponse)
      .then((d: any) => d.data)
      .catch(() => false);
  },
  async getLimitAnalysis(params?: {
    trade_date?: string;
    exchange?: string;
    board?: string;
  }): Promise<any> {
    return request
      .get("/quantTrade/market/limit-analysis", { params })
      .then(handleResponse)
      .then((d: any) => d.data);
  },
};
