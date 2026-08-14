// Market 模块 TypeScript 类型定义

export interface IndexOverviewItem {
  code: string;
  name: string;
  close: number | null;
  pct_chg: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  vol: number | null;
  amount: number | null;
}

export interface IndustryHeatmapItem {
  code: string;
  name: string;
  pct_chg: number | null;
  pct_chg_5d?: number | null;
  pct_chg_20d?: number | null;
}

export interface MarketBreadth {
  up: number;
  down: number;
  flat: number;
  total: number;
  limit_up: number;
  limit_down: number;
}

export interface TopVolumeItem {
  ts_code: string;
  name: string;
  industry?: string | null;
  close: number | null;
  pct_chg: number | null;
  amount: number | null;
  vol?: number | null;
  pe?: number | null;
  pb?: number | null;
  total_mv?: number | null;
  circ_mv?: number | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
}

export interface TopMoneyflowItem {
  ts_code: string;
  name: string;
  net_mf_amount: number | null;
  close?: number | null;
  pct_chg?: number | null;
  buy_elg_amount?: number | null;
  sell_elg_amount?: number | null;
  buy_lg_amount?: number | null;
  sell_lg_amount?: number | null;
  buy_md_amount?: number | null;
  sell_md_amount?: number | null;
  buy_sm_amount?: number | null;
  sell_sm_amount?: number | null;
}

export interface HsgtFlowItem {
  trade_date: string | null;
  net_inflow: number | null;
  sh_inflow: number | null;
  sz_inflow: number | null;
}

export interface MacroLatestItem {
  date: string | null;
  cpi_yoy?: number | null;
  ppi_yoy?: number | null;
  gdp_yoy?: number | null;
}

export interface IndustryTrendSeries {
  name: string;
  code: string;
  data: (number | null)[];
}

export interface IndustryTrendResponse {
  dates: string[];
  series: IndustryTrendSeries[];
  total_industries: number;
}

export interface SwHeatmapItem {
  code: string;
  name: string;
  pct_1d?: number | null;
  pct_5d?: number | null;
  pct_10d?: number | null;
  pct_20d?: number | null;
  pct_30d?: number | null;
  pct_60d?: number | null;
  amount?: number | null;
}

export interface DashboardOverview {
  data_date: string | null;
  indices: IndexOverviewItem[];
  industry_heatmap: IndustryHeatmapItem[];
  market_breadth: MarketBreadth;
  top_volume: TopVolumeItem[];
  top_moneyflow: TopMoneyflowItem[];
  hsgt_flow: HsgtFlowItem | null;
  sw_heatmap?: SwHeatmapItem[];
  macro_latest?: {
    cpi?: MacroLatestItem | null;
    ppi?: MacroLatestItem | null;
    gdp?: MacroLatestItem | null;
  } | null;
}

// StockDetail
export interface StockBasicInfo {
  ts_code: string;
  name: string;
  industry?: string;
  list_date?: string;
  delist_date?: string;
  is_st: boolean;
  fullname?: string;
  area?: string;
  market?: string;
  symbol?: string;
  exchange?: string;
  list_status?: string;
  chair_man?: string;
  employees?: number;
  province?: string;
  city?: string;
  website?: string;
  sw_l1?: string;
  sw_l3?: string;
}

export interface StockLatestQuote {
  trade_date: string;
  close: number | null;
  pct_chg: number | null;
  vol: number | null;
  amount: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
}

export interface StockLatestBasic {
  pe: number | null;
  pb: number | null;
  total_mv: number | null;
  circ_mv: number | null;
  turnover_rate: number | null;
  volume_ratio: number | null;
}

export interface StockLimitPrice {
  up_limit: number | null;
  down_limit: number | null;
  pre_close: number | null;
}

export interface KLineItem {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  vol: number | null;
  amount: number | null;
  pct_chg?: number | null;
}

export interface StockQuotesGroup {
  daily: KLineItem[];
  weekly: KLineItem[];
  monthly: KLineItem[];
}

export interface StockMoneyflowItem {
  trade_date: string;
  net_mf_amount: number | null;
  buy_lg_amount?: number | null;
  sell_lg_amount?: number | null;
  buy_elg_amount?: number | null;
  sell_elg_amount?: number | null;
  buy_md_amount?: number | null;
  sell_md_amount?: number | null;
  buy_sm_amount?: number | null;
  sell_sm_amount?: number | null;
}

export interface FinancialIndicator {
  end_date: string;
  roe?: number | null;
  roa?: number | null;
  grossprofit_margin?: number | null;
  netprofit_margin?: number | null;
  debt_to_assets?: number | null;
  eps?: number | null;
  bps?: number | null;
  current_ratio?: number | null;
  quick_ratio?: number | null;
}

export interface TopHolderItem {
  end_date: string;
  holder_name: string;
  hold_num: number | null;
  hold_ratio: number | null;
}

export interface HoldernumberItem {
  end_date: string;
  holder_num: number | null;
}

export interface StockFullResponse {
  basic: StockBasicInfo | null;
  latest_quote: StockLatestQuote | null;
  latest_basic: StockLatestBasic | null;
  limit_price: StockLimitPrice | null;
  quotes: StockQuotesGroup;
  moneyflow: StockMoneyflowItem[];
  financial: Record<string, any>;
  shareholders: Record<string, any>;
  factors: Record<string, any>;
  risk: Record<string, any>;
}

// Screener
export interface ScreenerParams {
  market?: string[];
  industry?: string[];
  pe_min?: number | null;
  pe_max?: number | null;
  pb_min?: number | null;
  pb_max?: number | null;
  mv_min?: number | null;
  mv_max?: number | null;
  roe_min?: number | null;
  pct_chg_min?: number | null;
  pct_chg_max?: number | null;
  turnover_min?: number | null;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  limit?: number;
}
export interface ScreenerResult {
  stocks: ScreenerStockItem[];
  total: number;
  page: number;
}
export interface ScreenerStockItem {
  ts_code: string;
  name: string;
  industry?: string;
  list_date?: string;
  close?: number;
  pct_chg?: number;
  amount?: number;
  vol?: number;
  pe?: number;
  pb?: number;
  total_mv?: number;
  turnover_rate?: number;
  roe?: number;
}

// Industry
export interface IndustryNode {
  code: string;
  name: string;
  level: string;
  parent_code?: string;
}
export interface IndustryDetail {
  info: IndustryHeatmapItem & { level?: string };
  members: {
    ts_code: string;
    name: string;
    close?: number;
    pct_chg?: number;
    amount?: number;
  }[];
}

export interface MarketStateResponse {
  dates: string[];
  regime_series: string[];
  breadth: number[];
  volatility: number[];
  momentum: number[];
  trend: number[];
  limit_dates: string[];
  limit_up: number[];
  limit_down: number[];
  latest: {
    regime: string;
    year_line_pct: number | null;
    volatility_pctl: number | null;
    breadth: number | null;
    volatility: number | null;
    momentum: number | null;
    trend: number | null;
  };
}

export interface StyleRotationResponse {
  index_dates: string[];
  index_series: Record<string, number[]>;
  index_names: Record<string, string>;
  industry_strength: { name: string; ret_30d: number }[];
}
