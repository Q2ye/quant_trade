-- seed_factor_definitions.sql
-- 因子定义种子数据 — 插入因子定义到 factor_definitions 表
-- 日期: 2026-06-22 (v2: factor_code 对齐计算器注册表 key)
-- 说明: factor_code 与 factor_calculators.py 中 @register_factor 的 name 一致
--       参数化因子(ma_5, ema_12 等)通过参数提取内建参数
--       中文 display_name 由 factor_name 字段提供

INSERT INTO factor_definitions (id, factor_code, factor_name, factor_type, category, description, formula, parameters, data_requirements, output_type, calculation_frequency, is_public, is_active) VALUES

-- ==================== 趋势类 ====================
('f0010000-0000-0000-0000-000000000001', 'ma_5',    '5日均线',        'technical', '趋势', '5日简单移动平均线', 'SMA(close, 5)', '{"window": 5}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000002', 'ma_20',   '20日均线',       'technical', '趋势', '20日简单移动平均线', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000003', 'ema_12',  '12日指数均线',    'technical', '趋势', '12日指数移动平均线', 'EMA(close, 12)', '{"window": 12}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000004', 'ema_26',  '26日指数均线',    'technical', '趋势', '26日指数移动平均线', 'EMA(close, 26)', '{"window": 26}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 动量类 ====================
('f0010000-0000-0000-0000-000000000005', 'macd',    'MACD',           'technical', '动量', 'MACD指标（12/26/9）', 'EMA(close,12)-EMA(close,26)', '{"fast": 12, "slow": 26, "signal": 9}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000006', 'rsi_14',  'RSI(14)',        'technical', '动量', '14日相对强弱指标', 'RSI(close, 14)', '{"window": 14}', '{"required": ["close"]}', 'float', 'daily', true, true),
-- v2: 对齐计算器注册表: momentum_Xm → ret_Xm (= StandardFactors.RET_XM)
('f0010000-0000-0000-0000-000000000007', 'ret_1m',  '1月动量',    'technical', '动量', '近1个月价格收益率', '(close - close_21d) / close_21d', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000008', 'ret_3m',  '3月动量',    'technical', '动量', '近3个月价格收益率', '(close - close_63d) / close_63d', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000009', 'ret_6m',  '6月动量',    'technical', '动量', '近6个月价格收益率', '(close - close_126d) / close_126d', '{"window": 126}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 波动率类 ====================
-- v2: 对齐计算器注册表: volatility_Xm → vol_Xm (= StandardFactors.VOLATILITY_XM)
('f0010000-0000-0000-0000-000000000010', 'vol_1m', '1月波动率',  'technical', '风险', '近1个月日收益率标准差(年化)', 'std(daily_return, 21) * sqrt(252)', '{"window": 21}', '{"required": ["close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000011', 'vol_3m', '3月波动率',  'technical', '风险', '近3个月日收益率标准差(年化)', 'std(daily_return, 63) * sqrt(252)', '{"window": 63}', '{"required": ["close"]}', 'float', 'daily', true, true),
-- v2: 对齐计算器注册表: boll_width → boll
('f0010000-0000-0000-0000-000000000012', 'boll', '布林带中轨',     'technical', '风险', '布林带中轨(20日均线)', 'SMA(close, 20)', '{"window": 20}', '{"required": ["close"]}', 'float', 'daily', true, true),

-- ==================== 成交量类 ====================
('f0010000-0000-0000-0000-000000000013', 'volume_ratio_5d',  '5日量比', 'technical', '情绪', '5日均成交量与20日均成交量比值', 'MA(vol,5) / MA(vol,20)', '{"short": 5, "long": 20}', '{"required": ["vol"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000014', 'turnover_5d',      '5日换手率','technical', '情绪', '5日平均换手率', 'MA(turnover_rate, 5)', '{"window": 5}', '{"required": ["turnover_rate"]}', 'float', 'daily', true, true),

-- ==================== 其他技术指标 ====================
('f0010000-0000-0000-0000-000000000015', 'kdj_k',   'KDJ-K',         'technical', '动量', 'KDJ指标K值(9,3,3)', 'SMA(RSV, 3)', '{"n": 9, "m1": 3, "m2": 3}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000016', 'atr_14',  'ATR(14)',       'technical', '风险', '14日平均真实波幅（当前使用收盘价代替）', 'MA(TR, 14)', '{"window": 14}', '{"required": ["high", "low", "close"]}', 'float', 'daily', true, true),

-- ==================== 估值类（基本面因子，依赖 financial_income 表） ====================
('f0010000-0000-0000-0000-000000000017', 'pe_ttm',  '市盈率(TTM)',   'fundamental', '估值', '滚动市盈率', 'market_cap / net_profit_ttm', '{}', '{"required": ["market_cap", "net_profit"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000018', 'pb',      '市净率',        'fundamental', '估值', '市净率', 'market_cap / book_value', '{}', '{"required": ["market_cap", "book_value"]}', 'float', 'daily', true, true),
('f0010000-0000-0000-0000-000000000019', 'roe',     '净资产收益率',    'fundamental', '质量', '净资产收益率', 'net_profit / equity', '{}', '{"required": ["net_profit", "equity"]}', 'float', 'monthly', true, true),
('f0010000-0000-0000-0000-000000000020', 'gross_margin', '毛利率',    'fundamental', '质量', '毛利率', '(revenue - cost) / revenue', '{}', '{"required": ["revenue", "cost"]}', 'float', 'monthly', true, true)
ON CONFLICT (factor_code) DO UPDATE SET
    factor_name = EXCLUDED.factor_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    parameters = EXCLUDED.parameters,
    data_requirements = EXCLUDED.data_requirements;
