// quant_web/src/api/events.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  StockBasicInfo,
  MoneyFlowData,
  QuoteDataResponse,
  FinancialDataResponse,
  StockListResponse,
  HistoricalDataResponse,
} from "@/types";
import { FinancialData, HistoricalDataPoint, StockBasic } from "@/types";
import type {
  ResearchTaskListResponse,
  ResearchTaskDetail,
  CancelResearchResponse,
} from "@/types/api-research";

// 定义股票列表返回结果的接口
interface StockListResult {
  stocks: StockBasic[];
  total: number;
  page: number;
}

/**
 * 数据管理API服务
 * 提供股票数据、财务数据、实时行情等数据查询功能
 */
const dataAPI = {
  /**
   * 获取市场概览数据
   * @returns 市场整体数据
   */
  async getMarketData(): Promise<any> {
    return request
      .get("/quantTrade/data/market-overview")
      .then(handleResponse)
      .then((data: { marketData: any }) => data.marketData);
  },

  /**
   * 获取历史行情数据
   * @param symbol 股票代码
   * @param period 时间周期
   * @param frequency 数据频率
   * @returns 历史数据点数组
   */
  async getHistoricalData(
    symbol: string,
    period: string = "1y",
    frequency: string = "1d",
  ): Promise<HistoricalDataPoint[]> {
    return request
      .get(`/quantTrade/data/stocks/${symbol}/history`, {
        params: { period, frequency },
      })
      .then(handleResponse)
      .then((data: HistoricalDataResponse) => {
        // 确保返回的是 HistoricalDataPoint[] 类型
        if (Array.isArray(data.data)) {
          return data.data as HistoricalDataPoint[];
        }
        // 如果后端返回的是 KLineData[]，需要进行转换
        console.warn("历史数据格式需要转换，当前返回类型:", typeof data.data);
        return [];
      });
  },

  /**
   * 获取财务数据
   * @param symbol 股票代码
   * @returns 财务数据数组
   */
  async getFinancialData(symbol: string): Promise<FinancialData[]> {
    return request
      .get(`/quantTrade/data/stocks/${symbol}/financial`)
      .then(handleResponse)
      .then((data: FinancialDataResponse) => {
        // 确保返回的是 FinancialData[] 类型
        if (Array.isArray(data.data)) {
          return data.data as FinancialData[];
        }
        console.warn("财务数据格式需要转换");
        return [];
      });
  },

  /**
   * 获取单个股票的财务数据（最新一期）
   * @param symbol 股票代码
   * @returns 最新财务数据
   */
  async getLatestFinancialData(symbol: string): Promise<FinancialData | null> {
    return request
      .get(`/quantTrade/data/financials/${symbol}/latest`)
      .then(handleResponse)
      .then((data: { financial: FinancialData }) => data.financial)
      .catch(() => null);
  },

  /**
   * 获取ETF数据列表
   * @returns ETF基本信息数组
   */
  async getETFData(): Promise<any[]> {
    return request
      .get("/quantTrade/data/etfs")
      .then(handleResponse)
      .then((data: { etfs: any[] }) => data.etfs);
  },

  /**
   * 获取股票基本信息
   * @param symbol 股票代码
   * @returns 股票基本信息
   */
  async getStockBasic(symbol: string): Promise<StockBasicInfo> {
    return request
      .get(`/quantTrade/data/stocks/${symbol}/basic`)
      .then(handleResponse)
      .then((data: { basic: StockBasicInfo }) => data.basic);
  },

  /**
   * 获取资金流向数据
   * @param symbol 股票代码
   * @param period 时间周期
   * @returns 资金流向数据
   */
  async getMoneyFlow(
    symbol: string,
    period: string = "1m",
  ): Promise<MoneyFlowData> {
    return request
      .get(`/quantTrade/data/stocks/${symbol}/moneyflow`, {
        params: { period },
      })
      .then(handleResponse)
      .then((data: { moneyflow: MoneyFlowData }) => data.moneyflow);
  },

  /**
   * 获取板块数据
   * @returns 板块信息数组
   */
  async getSectorData(): Promise<any[]> {
    return request
      .get("/quantTrade/data/sectors")
      .then(handleResponse)
      .then((data: { sectors: any[] }) => data.sectors);
  },

  /**
   * 获取指数成分股
   * @param indexCode 指数代码
   * @returns 成分股代码数组
   */
  async getIndexComponents(indexCode: string): Promise<string[]> {
    return request
      .get(`/quantTrade/data/indexes/${indexCode}/components`)
      .then(handleResponse)
      .then((data: { components: string[] }) => data.components);
  },

  /**
   * 获取股票列表
   * @param exchange 交易所
   * @param industry 行业
   * @param page 页码
   * @param pageSize 每页大小
   * @returns 股票列表结果
   */
  async getStockList(
    exchange: string = "",
    industry: string = "",
    page: number = 1,
    pageSize: number = 50,
  ): Promise<StockBasic[]> {
    return request
      .get("/quantTrade/data/stocks", {
        params: { exchange, industry, page, pageSize },
      })
      .then(handleResponse)
      .then((data: StockListResponse) => {
        // 直接返回股票数组，而不是包含分页信息的对象
        if (Array.isArray(data.data)) {
          return data.data as StockBasic[];
        }
        // 如果后端返回的是分页结构，提取 items 数组
        if (data.data && Array.isArray((data.data as any).items)) {
          return (data.data as any).items as StockBasic[];
        }
        console.warn("股票列表数据格式异常");
        return [];
      });
  },

  /**
   * 获取股票列表（包含分页信息）
   * @param exchange 交易所
   * @param industry 行业
   * @param page 页码
   * @param pageSize 每页大小
   * @returns 包含分页信息的股票列表结果
   */
  async getStockListWithPagination(
    exchange: string = "",
    industry: string = "",
    page: number = 1,
    pageSize: number = 50,
  ): Promise<StockListResult> {
    return request
      .get("/quantTrade/data/stocks", {
        params: { exchange, industry, page, pageSize },
      })
      .then(handleResponse)
      .then((data: StockListResponse) => {
        // 处理分页响应
        if (data.data && Array.isArray((data.data as any).items)) {
          const paginatedData = data.data as any;
          return {
            stocks: paginatedData.items as StockBasic[],
            total: paginatedData.total || 0,
            page: paginatedData.page || page,
          };
        }
        // 如果返回的是纯数组，则包装为分页格式
        if (Array.isArray(data.data)) {
          return {
            stocks: data.data as StockBasic[],
            total: data.data.length,
            page: page,
          };
        }
        console.warn("股票分页列表数据格式异常");
        return { stocks: [], total: 0, page };
      });
  },

  /**
   * 搜索股票
   * @param keyword 搜索关键词
   * @returns 搜索结果数组
   */
  async searchStocks(keyword: string): Promise<StockBasic[]> {
    return request
      .get("/quantTrade/data/stocks", {
        params: { keyword },
      })
      .then(handleResponse)
      .then((data: { results: StockBasic[] }) => data.results || []);
  },

  /**
   * 获取因子数据（需要指定股票代码和日期范围）
   * @param tsCode 股票代码，如 "000001.SZ"
   * @param factorName 因子名称筛选（可选）
   * @param startDate 开始日期
   * @param endDate 结束日期
   * @returns 因子数据
   */
  async getFactorData(
    tsCode: string,
    factorName: string | null = null,
    startDate: string,
    endDate: string,
  ): Promise<{
    factor_values: Array<{ factor_name: string; value: number; date: string }>;
    metadata: any; statistics: any;
  }> {
    return request
      .get("/quantTrade/data/factors", {
        params: {
          ts_code: tsCode,
          factor_name: factorName,
          start_date: startDate,
          end_date: endDate,
          page: 1,
          page_size: 100,
        },
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 获取因子元数据（可用因子列表及其分类/描述/公式）
   */
  async getFactorMetadata(params?: {
    factor_category?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<{
    metadata_list: Array<{
      factor_name: string; display_name: string; description: string;
      category: string; formula?: string; data_source?: string;
    }>;
    summary: { total_factors: number; by_category: Record<string, number> };
  }> {
    return request
      .get("/quantTrade/data/factors/metadata", { params })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 提交因子研究任务
   */
  async submitFactorResearch(params: {
    stock_codes?: string[];
    factor_names?: string[];
    factor_category?: string;
    universe?: string[];
    basket_ids?: string[];
    start_date?: string;
    end_date?: string;
  }): Promise<{ research_id: string; message?: string; parameters?: Record<string, any> }> {
    return request
      .post("/quantTrade/data/factors/research", params)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 查询因子研究任务状态
   */
  async getResearchStatus(params?: {
    research_id?: string;
  }): Promise<any> {
    return request
      .get("/quantTrade/data/factors/research/status", { params })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 获取最近的因子研究任务列表
   */
  async getRecentResearchTasks(): Promise<ResearchTaskListResponse> {
    return request
      .get("/quantTrade/data/factors/research/status")
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 获取因子研究任务详情
   * @param researchId 研究任务ID
   */
  async getResearchTaskDetail(researchId: string): Promise<ResearchTaskDetail> {
    return request
      .get("/quantTrade/data/factors/research/status", {
        params: { research_id: researchId },
      })
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 取消因子研究任务
   * @param researchId 研究任务ID
   */
  async cancelFactorResearch(researchId: string): Promise<CancelResearchResponse> {
    return request
      .post(`/quantTrade/data/factors/research/${researchId}/cancel`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },
  async deleteFactorResearch(researchId: string): Promise<{ success: boolean; message: string }> {
    return request
      .delete(`/quantTrade/data/factors/research/${researchId}`)
      .then(handleResponse)
      .then((res: any) => res.data ?? res);
  },

  /**
   * 获取数据同步状态
   * @returns 同步状态信息
   */
  async getDataSyncStatus(): Promise<string> {
    return request
      .get("/quantTrade/data/sync/status")
      .then(handleResponse)
      .then((data: { status: string }) => data.status);
  },

  /**
   * 触发数据同步
   * @param source 数据源
   * @returns 无返回值
   */
  async triggerDataSync(source: string): Promise<void> {
    return request
      .post("/quantTrade/data/sync/batch", { source })
      .then(handleResponse);
  },

  /**
   * 创建因子定义
   */
  async createFactorDefinition(params: {
    factor_code: string;
    factor_name: string;
    factor_type?: string;
    category?: string;
    description?: string;
    formula?: string;
    parameters?: Record<string, any>;
    data_requirements?: string[];
    is_public?: boolean;
    is_active?: boolean;
  }): Promise<{ success: boolean; data?: any; message: string }> {
    return request
      .post("/quantTrade/data/factors/definition", params)
      .then(handleResponse);
  },

  /**
   * 更新因子定义
   */
  async updateFactorDefinition(
    factorId: string,
    params: Record<string, any>,
  ): Promise<{ success: boolean; message: string }> {
    return request
      .put(`/quantTrade/data/factors/definition/${factorId}`, params)
      .then(handleResponse);
  },

  /**
   * 删除（停用）因子定义
   */
  async deleteFactorDefinition(
    factorId: string,
  ): Promise<{ success: boolean; message: string }> {
    return request
      .delete(`/quantTrade/data/factors/definition/${factorId}`)
      .then(handleResponse);
  },
};

/**
 * 实时数据订阅服务（模拟实现）
 */
export class RealtimeDataService {
  private subscribers: Map<
    string,
    Array<(symbol: string, quote: any) => void>
  > = new Map();
  private intervals: Map<string, NodeJS.Timeout> = new Map();
  private _useMock: boolean;

  constructor() {
    // 仅当显式设置 VITE_USE_MOCK_QUOTES=true 时启用模拟行情
    this._useMock = import.meta.env.VITE_USE_MOCK_QUOTES === "true";
    if (this._useMock) {
      console.warn("RealtimeDataService: 使用模拟行情数据（VITE_USE_MOCK_QUOTES=true）");
    }
  }

  /**
   * 订阅实时数据
   * @param symbols 股票代码数组
   * @param callback 回调函数
   */
  subscribeRealtime(
    symbols: string[],
    callback: (symbol: string, quote: any) => void,
  ) {
    symbols.forEach((symbol) => {
      if (!this.subscribers.has(symbol)) {
        this.subscribers.set(symbol, []);
      }
      this.subscribers.get(symbol)!.push(callback);

      // 仅在模拟模式下启动定时器生成假行情
      if (this._useMock && !this.intervals.has(symbol)) {
        const interval = setInterval(() => {
          this.generateMockQuote(symbol);
        }, 2000);
        this.intervals.set(symbol, interval);
      }
    });
  }

  /**
   * 取消订阅实时数据
   * @param symbols 股票代码数组
   * @param callback 回调函数（可选，不指定则取消所有回调）
   */
  unsubscribeRealtime(
    symbols: string[],
    callback?: (symbol: string, quote: any) => void,
  ) {
    symbols.forEach((symbol) => {
      if (this.subscribers.has(symbol)) {
        if (callback) {
          const callbacks = this.subscribers.get(symbol)!;
          const index = callbacks.indexOf(callback);
          if (index > -1) {
            callbacks.splice(index, 1);
          }
          if (callbacks.length === 0) {
            this.subscribers.delete(symbol);
            this.clearInterval(symbol);
          }
        } else {
          this.subscribers.delete(symbol);
          this.clearInterval(symbol);
        }
      }
    });
  }

  /**
   * 生成模拟行情数据
   * @param symbol 股票代码
   */
  private generateMockQuote(symbol: string) {
    const change = (Math.random() - 0.5) * 2;
    const price = 100 + Math.random() * 50;
    const quote = {
      symbol,
      price: parseFloat(price.toFixed(2)),
      change: parseFloat(change.toFixed(2)),
      changePercent: parseFloat(((change / price) * 100).toFixed(2)),
      volume: Math.floor(Math.random() * 1000000),
      time: new Date().toISOString(),
    };

    // 通知所有订阅者
    const callbacks = this.subscribers.get(symbol);
    if (callbacks) {
      callbacks.forEach((callback) => {
        callback(symbol, quote);
      });
    }
  }

  /**
   * 清理定时器
   * @param symbol 股票代码
   */
  private clearInterval(symbol: string) {
    const interval = this.intervals.get(symbol);
    if (interval) {
      clearInterval(interval);
      this.intervals.delete(symbol);
    }
  }

  /**
   * 销毁服务，清理所有资源
   */
  destroy() {
    this.intervals.forEach((interval, symbol) => {
      clearInterval(interval);
    });
    this.intervals.clear();
    this.subscribers.clear();
  }
}

// 创建默认的实时数据服务实例
export const defaultRealtimeService = new RealtimeDataService();

// 获取股票实时行情（BasketDetail 等页面使用）
export async function fetchStockRealTime(
  codes: string[],
): Promise<
  Record<string, { price: number; change: number; changePercent: number }>
> {
  return request
    .post("/quantTrade/data/realtime", { codes })
    .then(handleResponse);
}

// 将实时数据服务方法添加到默认导出对象中
export default {
  ...dataAPI,
  subscribeRealtime: defaultRealtimeService.subscribeRealtime.bind(
    defaultRealtimeService,
  ),
  unsubscribeRealtime: defaultRealtimeService.unsubscribeRealtime.bind(
    defaultRealtimeService,
  ),
};
