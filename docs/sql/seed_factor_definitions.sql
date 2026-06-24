-- seed_factor_definitions.sql
-- 日期: 2026-06-23 (v3: factor_code 统一对齐 StandardFactors 大写定义 — 单一真相源)
-- 说明: factor_code 与 constants.py StandardFactors + factor_calculators.py @register_factor 的 name 严格一致
--       参数化因子(ma_5, ema_12 等)通过参数提取内建参数，对应基础因子 MA/EMA/RSI 等

-- 清理旧的大小写重复数据
DELETE FROM factor_definitions;

INSERT INTO factor_definitions (id, factor_code, factor_name, factor_type, category, description, formula, parameters, data_requirements, output_type, calculation_frequency, is_public, is_active) VALUES

-- ==================== 趋势类 ====================
('f0010000-0000-0000-0000-000000000001', 'ma_5',    '5日均线',        'technical', '趋势', '5日简单移动平均线', 'SMA(close, 5)', '{"window": 5}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000002', 'ma_20',   '20日均线',       'technical', '趋势', '20日简单移动平均线', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000003', 'ema_12',  '12日指数均线',    'technical', '趋势', '12日指数移动平均线', 'EMA(close, 12)', '{"window": 12}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000004', 'ema_26',  '26日指数均线',    'technical', '趋势', '26日指数移动平均线', 'EMA(close, 26)', '{"window": 26}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 动量类 ====================
('f0010000-0000-0000-0000-000000000005', 'MACD',    'MACD',           'technical', '动量', 'MACD指标（12/26/9）', 'EMA(close,12)-EMA(close,26)', '{"fast": 12, "slow": 26, "signal": 9}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000006', 'rsi_14',  'RSI(14)',        'technical', '动量', '14日相对强弱指标', 'RSI(close, 14)', '{"window": 14}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000007', 'RET_1M',  '1月动量',    'technical', '动量', '近1个月价格收益率', '(close - close_21d) / close_21d', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000008', 'RET_3M',  '3月动量',    'technical', '动量', '近3个月价格收益率', '(close - close_63d) / close_63d', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000009', 'RET_6M',  '6月动量',    'technical', '动量', '近6个月价格收益率', '(close - close_126d) / close_126d', '{"window": 126}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 波动率类 ====================
('f0010000-0000-0000-0000-000000000010', 'VOL_1M', '1月波动率',  'technical', '风险', '近1个月日收益率标准差(年化)', 'std(daily_return, 21) * sqrt(252)', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000011', 'VOL_3M', '3月波动率',  'technical', '风险', '近3个月日收益率标准差(年化)', 'std(daily_return, 63) * sqrt(252)', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000012', 'BOLL', '布林带中轨',     'technical', '风险', '布林带中轨(20日均线)', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 成交量/流动性 ====================
('f0010000-0000-0000-0000-000000000013', 'VOLUME_RATIO',  '5日量比', 'technical', '情绪', '5日均成交量与20日均成交量比值', 'MA(vol,5) / MA(vol,20)', '{"short": 5, "long": 20}', '{"required": ["vol"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000014', 'TURNOVER_RATE',      '5日换手率','technical', '情绪', '5日平均换手率', 'MA(turnover_rate, 5)', '{"window": 5}', '{"required": ["turnover_rate"]}', 'float', 'daily', true, true),

-- ==================== 其他技术指标 ====================
('f0010000-0000-0000-0000-000000000015', 'KDJ',   'KDJ-K',         'technical', '动量', 'KDJ指标K值(9,3,3)', 'SMA(RSV, 3)', '{"n": 9, "m1": 3, "m2": 3}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000016', 'ATR',  'ATR(14)',       'technical', '风险', '14日平均真实波幅', 'MA(TR, 14)', '{"window": 14}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),

-- ==================== 估值类 ====================
('f0010000-0000-0000-0000-000000000017', 'PE',  '市盈率(TTM)',   'fundamental', '估值', '滚动市盈率', 'market_cap / net_profit_ttm', '{}', '{"required": ["close", "eps"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000018', 'PB',      '市净率',        'fundamental', '估值', '市净率', 'market_cap / book_value', '{}', '{"required": ["close", "bps"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000033', 'PS',      '市销率',        'fundamental', '估值', '市销率（待实现：需营收+总股本数据）', 'market_cap / revenue', '{}', '{"required": ["close", "revenue", "total_shares"]}', 'float', 'daily', true, true),

-- ==================== 质量类 ====================
('f0010000-0000-0000-0000-000000000019', 'ROE',     '净资产收益率',    'fundamental', '质量', '净资产收益率', 'net_profit / equity', '{}', '{"required": ["n_income", "total_hldr_eqy"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000020', 'GM', '毛利率',    'fundamental', '质量', '毛利率', '(revenue - cost) / revenue', '{}', '{"required": ["revenue", "oper_cost"]}', 'float', 'monthly', true, true),

-- ==================== 补全：基本面因子 ====================
('f0010000-0000-0000-0000-000000000021', 'ROA',     '总资产收益率',   'fundamental', '质量', '净利润/总资产', 'net_income / total_assets', '{}', '{"required": ["n_income", "total_assets"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000022', 'OM',      '净利率',        'fundamental', '质量', '净利润/营业收入', 'net_income / revenue', '{}', '{"required": ["n_income", "revenue"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000023', 'DR',      '资产负债率',     'fundamental', '风险', '总负债/总资产', 'total_liab / total_assets', '{}', '{"required": ["total_liab", "total_assets"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000024', 'CURRENT_RATIO', '流动比率', 'fundamental', '风险', '流动资产/流动负债', 'cur_assets / cur_liab', '{}', '{"required": ["total_cur_assets", "total_cur_liab"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000025', 'QUICK_RATIO',   '速动比率', 'fundamental', '风险', '(流动资产-存货)/流动负债', '(cur_assets - inventories) / cur_liab', '{}', '{"required": ["total_cur_assets", "inventories", "total_cur_liab"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000026', 'MC',      '流通市值',      'fundamental', '规模', '收盘价×流通股本', 'close * float_shares', '{}', '{"required": ["close", "float_shares"]}', 'float', 'daily', true, true),

-- ==================== 补全：动量/波动/技术 ====================
('f0010000-0000-0000-0000-000000000027', 'RET_12M', '12月动量',    'technical', '动量', '近12个月价格收益率', '(close - close_252d) / close_252d', '{"window": 252}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000028', 'VOL_12M', '12月波动率',  'technical', '风险', '近12个月日收益率标准差(年化)', 'std(daily_return, 252) * sqrt(252)', '{"window": 252}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000029', 'SHARPE_RATIO', '滚动夏普比率', 'technical', '风险', '(年化收益-无风险利率)/年化波动率', '(annual_ret - rf) / annual_vol', '{"window": 252, "risk_free_rate": 0.03}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000034', 'BETA',    'Beta系数',      'technical', '风险', '个股相对市场的系统性风险，基于60日滚动窗口', 'cov(ret_i, ret_m) / var(ret_m)', '{"window": 60}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 补全：基础版本（无参数后缀）====================
('f0010000-0000-0000-0000-000000000030', 'MA',     '20日均线(默认)', 'technical', '趋势', '20日简单移动平均线', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000031', 'EMA',    '12日指数均线(默认)', 'technical', '趋势', '12日指数移动平均线', 'EMA(close, 12)', '{"window": 12}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000032', 'RSI',    'RSI(14)',      'technical', '动量', '14日相对强弱指标', 'RSI(close, 14)', '{"window": 14}', '{"required": ["close"]}', 'float', 'daily', true, true)
ON CONFLICT (factor_code) DO UPDATE SET
    factor_name = EXCLUDED.factor_name,
    factor_type = EXCLUDED.factor_type,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    parameters = EXCLUDED.parameters,
    data_requirements = EXCLUDED.data_requirements,
    output_type = EXCLUDED.output_type,
    calculation_frequency = EXCLUDED.calculation_frequency;
    -- 注意: is_public 和 is_active 不在此处更新，由用户通过 API 控制
