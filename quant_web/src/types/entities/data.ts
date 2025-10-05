// quant_web/src/types/entities/data.ts
/**
 * 基础实体类型定义 - 用于数据库层和业务逻辑层
 */

/**
 * 股票基础信息表
 */
export interface StockBasic {
  ts_code: string;           // TS唯一代码 (主键)
  symbol: string;            // 股票代码
  name: string;              // 股票名称
  area?: string;             // 地域
  industry?: string;         // 所属行业
  fullname?: string;         // 股票全称
  enname?: string;           // 英文全称
  cnspell?: string;          // 拼音缩写
  market: string;            // 市场类型
  exchange?: string;         // 交易所
  curr_type?: string;        // 交易货币
  list_status?: string;      // 上市状态
  list_date: string;         // 上市日期
  delist_date?: string;      // 退市日期
  is_hs?: string;           // 沪深港通
  act_name?: string;         // 实控人名称
  act_ent_type?: string;     // 实控人企业性质
  created_at?: string;       // 创建时间
  updated_at?: string;       // 更新时间
}

/**
 * 上市公司基本信息表
 */
export interface StockCompany {
  ts_code: string;           // 股票代码
  com_name: string;          // 公司全称
  com_id: string;            // 统一社会信用代码
  exchange: string;          // 交易所代码
  chairman?: string;         // 法人代表
  manager?: string;          // 总经理
  secretary?: string;        // 董秘
  reg_capital: number;       // 注册资本(万元)
  setup_date: string;        // 注册日期
  province?: string;         // 所在省份
  city?: string;            // 所在城市
  introduction?: string;     // 公司介绍
  website?: string;         // 公司主页
  email?: string;           // 电子邮件
  office?: string;          // 办公室地址
  employees?: number;       // 员工人数
  main_business?: string;   // 主要业务及产品
  business_scope?: string;  // 经营范围
  created_at?: string;      // 创建时间
  updated_at?: string;      // 更新时间
}

/**
 * A股日线行情表
 */
export interface StockDaily {
  id: number;               // 主键ID
  ts_code: string;          // 股票代码
  trade_date: string;       // 交易日期
  open: number;            // 开盘价
  high: number;            // 最高价
  low: number;             // 最低价
  close: number;           // 收盘价
  pre_close: number;       // 昨收价
  change: number;          // 涨跌额
  pct_chg: number;         // 涨跌幅
  vol: number;             // 成交量
  amount: number;          // 成交额
  created_time?: string;   // 创建时间
  updated_time?: string;   // 更新时间
}

/**
 * 股票分钟行情表
 */
export interface StockMinutes {
  id: number;               // 主键ID
  ts_code: string;          // 股票代码
  freq: string;            // 分钟频度
  trade_time: string;       // 交易时间
  open: number;            // 开盘价
  high: number;            // 最高价
  low: number;             // 最低价
  close: number;           // 收盘价
  vol: number;             // 成交量
  amount: number;          // 成交金额
  created_time?: string;   // 创建时间
}

/**
 * 个股资金流向表
 */
export interface StockMoneyflow {
  id: number;               // 主键ID
  ts_code: string;          // 股票代码
  trade_date: string;       // 交易日期
  buy_sm_vol: number;      // 小单买入量
  buy_sm_amount: number;   // 小单买入金额
  sell_sm_vol: number;     // 小单卖出量
  sell_sm_amount: number;  // 小单卖出金额
  buy_md_vol: number;      // 中单买入量
  buy_md_amount: number;   // 中单买入金额
  sell_md_vol: number;     // 中单卖出量
  sell_md_amount: number;  // 中单卖出金额
  buy_lg_vol: number;      // 大单买入量
  buy_lg_amount: number;   // 大单买入金额
  sell_lg_vol: number;     // 大单卖出量
  sell_lg_amount: number;  // 大单卖出金额
  buy_elg_vol: number;     // 特大单买入量
  buy_elg_amount: number;  // 特大单买入金额
  sell_elg_vol: number;    // 特大单卖出量
  sell_elg_amount: number; // 特大单卖出金额
  net_mf_vol: number;      // 净流入量
  net_mf_amount: number;   // 净流入额
  total_vol: number;       // 总成交量
  buy_ratio: number;       // 买入占比
  large_net_ratio: number; // 大单净流入占比
  created_time?: string;   // 创建时间
  updated_time?: string;   // 更新时间
}

/**
 * ETF基础信息
 */
export interface ETFBasic {
  ts_code: string;          // 基金交易代码
  csname: string;           // ETF中文简称
  extname: string;          // ETF扩位交易所简称
  cname: string;           // 基金中文全称
  index_code?: string;     // 跟踪指数代码
  index_name?: string;     // 基准指数中文全称
  setup_date: string;      // 设立日期
  list_date?: string;      // 上市日期
  list_status: string;     // 存续状态
  exchange: string;        // 交易所
  mgr_name: string;        // 基金管理人简称
  custod_name: string;     // 基金托管人名称
  mgt_fee?: number;       // 基金管理费率
  etf_type: string;       // 投资通道类型
}

/**
 * ETF日线行情
 */
export interface ETFDaily {
  ts_code: string;          // ETF交易代码
  trade_date: string;       // 交易日期
  open: number;            // 开盘价
  high: number;            // 最高价
  low: number;             // 最低价
  close: number;           // 收盘价
  pre_close: number;       // 昨收盘价
  change: number;          // 涨跌额
  pct_chg: number;         // 涨跌幅
  vol: number;             // 成交量
  amount: number;          // 成交额
}

/**
 * 数据同步任务记录表
 */
export interface DataSyncTask {
  id: number;               // 主键ID
  task_type: string;        // 任务类型
  status: string;          // 任务状态
  start_time?: string;     // 开始时间
  end_time?: string;       // 结束时间
  total_records: number;   // 同步记录数
  error_message?: string;  // 错误信息
  created_at?: string;     // 创建时间
}

/**
 * 数据同步请求参数
 */
export interface DataSyncRequest {
  task_type: string;        // 任务类型
  start_date?: string;      // 开始日期
  end_date?: string;        // 结束日期
  ts_codes?: string[];      // 股票代码列表
  force_update?: boolean;   // 强制更新
}

/**
 * 数据查询参数
 */
export interface DataQueryParams {
  ts_code?: string;        // 股票代码
  trade_date?: string;     // 交易日期
  start_date?: string;     // 开始日期
  end_date?: string;       // 结束日期
  fields?: string[];       // 查询字段
  limit?: number;          // 限制条数
  offset?: number;         // 偏移量
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  data: T[];               // 数据列表
  total: number;           // 总记录数
  page: number;           // 当前页码
  page_size: number;      // 每页大小
  total_pages: number;    // 总页数
}

/**
 * 市场数据概览
 */
export interface MarketOverview {
  total_market_cap: number;        // 总市值
  trading_volume: number;          // 成交量
  trading_amount: number;          // 成交额
  advance_count: number;           // 上涨家数
  decline_count: number;           // 下跌家数
  unchanged_count: number;         // 平盘家数
  limit_up_count: number;          // 涨停家数
  limit_down_count: number;        // 跌停家数
  timestamp: string;               // 时间戳
}

/**
 * 财务指标数据 - 统一实体
 */
export interface FinancialData {
  symbol: string;                    // 股票代码
  report_date: string;               // 报告期
  eps: number;                       // 每股收益
  bps: number;                       // 每股净资产
  roe: number;                       // 净资产收益率
  profit_margin: number;             // 销售净利率
  debt_to_asset: number;             // 资产负债率
  revenue: number;                   // 营业收入
  net_profit: number;                // 净利润
  total_assets: number;              // 总资产
}

/**
 * 历史数据点 - 统一实体
 */
export interface HistoricalDataPoint {
  // 基础标识字段
  ts_code: string;                   // 股票/ETF代码
  trade_date: string;                // 交易日期 (YYYY-MM-DD)
  trade_time?: string;               // 交易时间 (对于分钟线数据)

  // 价格数据
  open: number;                      // 开盘价
  high: number;                      // 最高价
  low: number;                       // 最低价
  close: number;                     // 收盘价
  pre_close: number;                 // 前收盘价
  change: number;                    // 涨跌额
  pct_chg: number;                   // 涨跌幅 (%)

  // 成交量数据
  volume: number;                    // 成交量 (手)
  amount: number;                    // 成交额 (千元)

  // 技术指标 (可选)
  turnover_rate?: number;            // 换手率 (%)
  turnover_rate_f?: number;          // 换手率(自由流通股) (%)
  volume_ratio?: number;             // 量比

  // 估值指标 (可选)
  pe?: number;                       // 市盈率
  pe_ttm?: number;                   // 市盈率(TTM)
  pb?: number;                       // 市净率
  ps?: number;                       // 市销率
  ps_ttm?: number;                   // 市销率(TTM)
  dv_ratio?: number;                 // 股息率 (%)
  dv_ttm?: number;                   // 股息率(TTM) (%)

  // 市值数据 (可选)
  total_share?: number;              // 总股本 (万股)
  float_share?: number;              // 流通股本 (万股)
  free_share?: number;               // 自由流通股本 (万股)
  total_mv?: number;                 // 总市值 (万元)
  circ_mv?: number;                  // 流通市值 (万元)

  // 资金流向数据 (可选)
  net_mf_amount?: number;            // 净流入额 (万元)
  net_mf_volume?: number;            // 净流入量 (手)
  buy_ratio?: number;                // 买入占比 (%)
  large_net_ratio?: number;          // 大单净流入占比 (%)

  // 频率信息
  frequency: '1min' | '5min' | '15min' | '30min' | '60min' | 'daily' | 'weekly' | 'monthly';

  // 系统字段
  created_at?: string;               // 创建时间
  updated_at?: string;               // 更新时间
}

/**
 * 实时行情数据
 */
export interface RealTimeQuote {
  ts_code: string;          // 股票代码
  current: number;          // 当前价格
  change: number;           // 涨跌额
  changePercent: number;    // 涨跌幅
  volume: number;           // 成交量
  amount: number;           // 成交额
  open: number;            // 开盘价
  high: number;            // 最高价
  low: number;             // 最低价
  pre_close: number;       // 前收盘价
  lastUpdate?: number;     // 最后更新时间戳
}

/**
 * 指数数据
 */
export interface IndexData {
  ts_code: string;          // 指数代码
  trade_date: string;       // 交易日期
  close: number;           // 收盘价
  change: number;          // 涨跌额
  changePercent: number;   // 涨跌幅
  volume: number;          // 成交量
  amount: number;          // 成交额
  open: number;           // 开盘价
  high: number;           // 最高价
  low: number;            // 最低价
  pre_close: number;      // 前收盘价
}