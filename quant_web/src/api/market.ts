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

/**
 * 市场数据API服务
 * 提供股票、指数、ETF等市场基础数据的查询功能
 */

export interface StockListResult {
  stocks: StockBasic[];
  total: number;
  page: number;
}

export default {
  /**
   * 获取股票列表
   * @param params 查询参数
   * @returns 股票列表结果
   */
  async getStocks(
    params?: StockQueryParams,
  ): Promise<PaginatedResponse<StockBasic>> {
    return request
      .get("/quantTrade/market/stocks", { params })
      .then((response: any) => handleResponse(response))
      .then((data: PaginatedResponse<StockBasic>) => data);
  },

  /**
   * 获取股票详细信息
   * @param code 股票代码
   * @returns 股票详细信息
   */
  async getStockDetail(code: string): Promise<StockBasic> {
    return request
      .get(`/market/stock/${code}`)
      .then((response: any) => handleResponse(response))
      .then((data: { stock: StockBasic }) => data.stock);
  },

  /**
   * 获取股票历史数据
   * @param code 股票代码
   * @param params 查询参数
   * @returns K线数据数组
   */
  async getStockHistory(
    code: string,
    params: QuoteQueryParams,
  ): Promise<KLineData[]> {
    return request
      .get(`/market/stock/${code}/history`, { params })
      .then((response: any) => handleResponse(response))
      .then((data: { historical: KLineData[] }) => data.historical);
  },

  /**
   * 获取ETF列表
   * @param params 分页参数
   * @returns ETF基本信息数组
   */
  async getETFs(params?: {
    page?: number;
    limit?: number;
  }): Promise<StockBasic[]> {
    return request
      .get("/quantTrade/market/etfs", { params })
      .then((response: any) => handleResponse(response))
      .then((data: { etfs: StockBasic[] }) => data.etfs);
  },

  /**
   * 获取ETF详细信息
   * @param code ETF代码
   * @returns ETF详细信息
   */
  async getETFDetail(code: string): Promise<StockBasic> {
    return request
      .get(`/market/etf/${code}`)
      .then((response: any) => handleResponse(response))
      .then((data: { etf: StockBasic }) => data.etf);
  },

  /**
   * 获取指数列表
   * @returns 指数信息数组
   */
  async getIndexes(): Promise<IndexInfo[]> {
    return request
      .get("/quantTrade/market/indexes")
      .then((response: any) => handleResponse(response))
      .then((data: { indexes: IndexInfo[] }) => data.indexes);
  },

  /**
   * 获取指数详细信息
   * @param code 指数代码
   * @returns 指数详细信息
   */
  async getIndexDetail(code: string): Promise<IndexInfo> {
    return request
      .get(`/market/index/${code}`)
      .then((response: any) => handleResponse(response))
      .then((data: { index: IndexInfo }) => data.index);
  },

  /**
   * 获取板块列表
   * @returns 板块信息数组
   */
  async getSectors(): Promise<SectorInfo[]> {
    return request
      .get("/quantTrade/market/sectors")
      .then((response: any) => handleResponse(response))
      .then((data: { sectors: SectorInfo[] }) => data.sectors);
  },

  /**
   * 获取财务数据
   * @param code 股票代码
   * @param params 财务查询参数
   * @returns 财务数据数组
   */
  async getFinancialData(
    code: string,
    params: { reportDate?: string },
  ): Promise<FinancialData[]> {
    return request
      .get(`/market/stock/${code}/financial`, { params })
      .then((response: any) => handleResponse(response))
      .then((data: { financial: FinancialData[] }) => data.financial);
  },
};
