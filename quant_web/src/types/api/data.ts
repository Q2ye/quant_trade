// quant_web/src/types/api/events.ts
import { ApiResponse } from "@/types";
import { PaginatedResponse, PaginationParams, TimeRangeParams } from "./base";

// 从统一实体导入类型
import {
  StockBasic,
  FinancialData,
  HistoricalDataPoint,
  MarketOverview,
  DataSyncTask as EntityDataSyncTask,
  DataSyncRequest as EntityDataSyncRequest,
  StockMoneyflow,
} from "@/types/entities/data";

/**
 * 股票查询参数
 */
export interface StockQueryParams extends PaginationParams {
  symbol?: string; // 股票代码
  name?: string; // 股票名称模糊查询
  industry?: string; // 行业筛选
  market?: string; // 市场筛选
  listStatus?: string; // 上市状态筛选
}

/**
 * 行情数据查询参数
 */
export interface QuoteQueryParams extends TimeRangeParams {
  symbol: string; // 股票代码
  frequency?:
    | "daily"
    | "weekly"
    | "monthly"
    | "1min"
    | "5min"
    | "15min"
    | "30min"
    | "60min"; // 数据频率
  fields?: string[]; // 返回字段
  adjust?: "none" | "qfq" | "hfq"; // 复权类型
}

/**
 * K线数据点
 */
export interface KLineData {
  timestamp: string; // 时间戳
  open: number; // 开盘价
  high: number; // 最高价
  low: number; // 最低价
  close: number; // 收盘价
  volume: number; // 成交量
  amount: number; // 成交额
  turnoverRate?: number; // 换手率
}

/**
 * 财务指标查询参数
 */
export interface FinancialQueryParams {
  symbol: string; // 股票代码
  reportDate?: string; // 报告期
  fields?: string[]; // 返回字段
}

/**
 * 数据同步任务参数 - API专用
 */
export interface DataSyncRequest {
  dataType: "daily" | "minute" | "financial" | "basic" | "index"; // 数据类型
  startDate: string; // 开始日期
  endDate: string; // 结束日期
  symbols?: string[]; // 指定股票代码
  forceUpdate?: boolean; // 强制更新
}

/**
 * 数据同步任务状态 - API专用
 */
export interface DataSyncTask {
  taskId: string; // 任务ID
  dataType: string; // 数据类型
  status: "pending" | "running" | "completed" | "failed"; // 任务状态
  progress: number; // 进度百分比
  totalRecords: number; // 总记录数
  processedRecords: number; // 已处理记录数
  startTime?: string; // 开始时间
  endTime?: string; // 结束时间
  errorMessage?: string; // 错误信息
}

/**
 * 指数信息
 */
export interface IndexInfo {
  code: string; // 指数代码
  name: string; // 指数名称
  market: string; // 市场
  publisher: string; // 发布机构
  category: string; // 指数类别
  baseDate: string; // 基期
  basePoint: number; // 基点
}

/**
 * 板块信息
 */
export interface SectorInfo {
  code: string; // 板块代码
  name: string; // 板块名称
  type: string; // 板块类型
  stockCount: number; // 成分股数量
}

/**
 * 历史数据查询参数
 */
export interface HistoricalDataQueryParams extends TimeRangeParams {
  symbols: string[]; // 股票代码列表
  frequency:
    | "1min"
    | "5min"
    | "15min"
    | "30min"
    | "60min"
    | "daily"
    | "weekly"
    | "monthly";
  fields?: string[]; // 指定返回字段
  adjust?: "qfq" | "hfq" | "none"; // 复权类型
  includeIndicators?: boolean; // 是否包含技术指标
  includeFinancials?: boolean; // 是否包含财务指标
}

/**
 * 历史数据响应
 */
export interface HistoricalDataResponse extends ApiResponse<
  HistoricalDataPoint[]
> {
  metadata: {
    symbol: string; // 股票代码
    frequency: string; // 数据频率
    adjustType: string; // 复权类型
    dataCount: number; // 数据点数量
    dateRange: {
      // 日期范围
      start: string;
      end: string;
    };
    fields: string[]; // 返回的字段列表
  };
}

/**
 * 多股票历史数据响应
 */
export interface MultiSymbolHistoricalDataResponse extends ApiResponse<{
  [symbol: string]: HistoricalDataPoint[];
}> {
  metadata: {
    symbols: string[]; // 股票代码列表
    frequency: string; // 数据频率
    dataCount: number; // 总数据点数量
    dateRange: {
      // 日期范围
      start: string;
      end: string;
    };
  };
}

/**
 * 历史数据统计信息
 */
export interface HistoricalDataStats {
  symbol: string; // 股票代码
  frequency: string; // 数据频率
  totalRecords: number; // 总记录数
  dateRange: {
    // 日期范围
    start: string;
    end: string;
  };
  priceStats: {
    // 价格统计
    min: number; // 最低价
    max: number; // 最高价
    avg: number; // 平均价
    std: number; // 标准差
  };
  volumeStats: {
    // 成交量统计
    min: number; // 最小成交量
    max: number; // 最大成交量
    avg: number; // 平均成交量
    total: number; // 总成交量
  };
  returnStats: {
    // 收益率统计
    totalReturn: number; // 总收益率
    annualReturn: number; // 年化收益率
    volatility: number; // 波动率
    sharpeRatio?: number; // 夏普比率
    maxDrawdown: number; // 最大回撤
  };
}

/**
 * 历史数据对比参数
 */
export interface HistoricalDataCompareParams {
  symbols: string[]; // 要对比的股票代码
  benchmark?: string; // 基准代码 (如指数)
  frequency: string; // 数据频率
  startDate: string; // 开始日期
  endDate: string; // 结束日期
  compareBy: "price" | "return" | "volume" | "volatility"; // 对比维度
  normalization?: "index" | "percent" | "zscore"; // 标准化方法
}

/**
 * 历史数据对比结果
 */
export interface HistoricalDataCompareResult {
  symbols: string[]; // 股票代码列表
  benchmark?: string; // 基准代码
  compareBy: string; // 对比维度
  data: {
    date: string; // 日期
    values: { [symbol: string]: number }; // 各股票的值
    benchmarkValue?: number; // 基准值
  }[];
  stats: {
    // 统计结果
    [symbol: string]: {
      mean: number; // 均值
      std: number; // 标准差
      min: number; // 最小值
      max: number; // 最大值
      sharpe?: number; // 夏普比率
      volatility: number; // 波动率
    };
  };
}

// API专用响应类型定义
export interface StockListResponse extends PaginatedResponse<StockBasic> {}
export interface StockDetailResponse extends ApiResponse<StockBasic> {}
export interface QuoteDataResponse extends ApiResponse<KLineData[]> {}
export interface FinancialDataResponse extends ApiResponse<FinancialData[]> {}
export interface DataSyncResponse extends ApiResponse<DataSyncTask> {}
export interface DataSyncListResponse extends PaginatedResponse<DataSyncTask> {}
export interface IndexListResponse extends ApiResponse<IndexInfo[]> {}
export interface SectorListResponse extends ApiResponse<SectorInfo[]> {}
export interface HistoricalDataResponse extends ApiResponse<
  HistoricalDataPoint[]
> {}
export interface HistoricalDataStatsResponse extends ApiResponse<HistoricalDataStats> {}
export interface HistoricalDataCompareResponse extends ApiResponse<HistoricalDataCompareResult> {}
export interface MarketStatusResponse extends ApiResponse<{
  isOpen: boolean; // 市场是否开市
  currentTime: string; // 当前时间
  nextOpenTime?: string; // 下次开市时间
  nextCloseTime?: string; // 下次收市时间
}> {}

// 为Vuex store保留的兼容类型
export interface StockBasicInfo extends StockBasic {}
export interface MoneyFlowData extends StockMoneyflow {}
