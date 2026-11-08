# 日频数据底座接口探针报告

> 生成时间：2026-11-08 15:52:12
> 按日接口取样日期（倒序尝试）：20261106, 20261105, 20261104, 20261103, 20261102, 20261030, 20261029, 20261028, 20261027, 20261026
> 区间接口：20260901 ~ 20261106；月度接口：202608 ~ 202610

| 接口 | 目标表 | 模式 | 状态 | 行数 | 字段 |
|:---|:---|:---|:--:|--:|:---|
| `fx_obasic` | `fx_basic` | catalog | ok | 69 | ts_code, name, classify, exchange, min_unit, max_unit, pip, pip_cost, traget_spread, min_stop_distance, trading_hours, break_time |
| `fx_daily` | `fx_daily` | date | ok | 101 | ts_code, trade_date, bid_open, bid_close, bid_high, bid_low, ask_open, ask_close, ask_high, ask_low, tick_qty |
| `fund_nav` | `fund_nav` | date | ok | 10500 | ts_code, ann_date, nav_date, unit_nav, accum_nav, accum_div, net_asset, adj_nav, update_flag |
| `fund_basic` | `fund_basic` | catalog | ok | 3014 | ts_code, name, management, custodian, fund_type, found_date, due_date, list_date, issue_date, delist_date, issue_amount, m_fee, c_fee, duration_year, p_value, min_amount, exp_return, benchmark, status, invest_type, type, trustee, purc_startdate, redm_startdate, market |
| `fund_company` | `fund_company` | catalog | ok | 214 | name, shortname, province, city, address, phone, office, website, chairman, manager, reg_capital, setup_date, end_date, employees, main_business, org_code, credit_code |
| `fund_manager` | `fund_manager` | catalog | ok | 19 | ts_code, ann_date, name, gender, birth_year, edu, nationality, begin_date, end_date, resume |
| `fund_div` | `fund_div` | custom | ok | 29 | ts_code, ann_date, imp_anndate, base_date, div_proc, record_date, ex_date, pay_date, earpay_date, net_ex_date, div_cash, base_unit, ear_distr, ear_amount, account_date, base_year |
| `fund_share` | `fund_share` | date | ok | 1752 | ts_code, trade_date, fd_share, fund_type, market |
| `fund_daily` | `fund_daily_ex` | date | ok | 2192 | ts_code, trade_date, pre_close, open, high, low, close, change, pct_chg, vol, amount |
| `margin_detail` | `stock_margin_detail` | date | ok | 2017 | trade_date, ts_code, rzye, rqye, rzmre, rqyl, rzche, rqchl, rqmcl, rzrqye |
| `margin_secs` | `stock_margin_secs` | date | ok | 4517 | trade_date, ts_code, name, exchange |
| `namechange` | `stock_namechange` | range | ok | 66 | ts_code, name, start_date, end_date, ann_date, change_reason |
| `new_share` | `stock_new_share` | range | ok | 24 | ts_code, sub_code, name, ipo_date, issue_date, amount, market_amount, price, pe, limit_amount, funds, ballot |
| `index_monthly` | `index_monthly` | custom | ok | 1000 | ts_code, trade_date, close, open, high, low, pre_close, change, pct_chg, vol, amount |
| `shibor` | `macro_rate` | range | ok | 45 | date, on, 1w, 2w, 1m, 3m, 6m, 9m, 1y |
| `libor` | `macro_rate` | custom | ok | 121 | date, curr_type, on, 1w, 1m, 2m, 3m, 6m, 12m |
| `hibor` | `macro_rate` | range | ok | 47 | date, on, 1w, 2w, 1m, 2m, 3m, 6m, 12m |
| `us_tbr` | `macro_rate` | range | ok | 47 | date, w4_bd, w4_ce, w8_bd, w8_ce, w13_bd, w13_ce, w26_bd, w26_ce, w52_bd, w52_ce, w17_bd, w17_ce |
| `us_tycr` | `macro_rate` | range | ok | 47 | date, m1, m2, m3, m6, y1, y2, y3, y5, y7, y10, y20, y30, m4 |
| `sf_month` | `macro_sf` | month | ok | 2 | month, inc_month, inc_cumval, stk_endval |
| `cn_m` | `macro_money` | month | ok | 2 | month, m0, m0_yoy, m0_mom, m1, m1_yoy, m1_mom, m2, m2_yoy, m2_mom |
| `cn_pmi` | `macro_pmi` | month | ok | 3 | month, pmi010000, pmi010100, pmi010200, pmi010300, pmi010400, pmi010401, pmi010402, pmi010403, pmi010500, pmi010501, pmi010502, pmi010503, pmi010600, pmi010601, pmi010602, pmi010603, pmi010700, pmi010701, pmi010702, pmi010703, pmi010800, pmi010801, pmi010802, pmi010803, pmi010900, pmi011000, pmi011100, pmi011200, pmi011300, pmi011400, pmi011500, pmi011600, pmi011700, pmi011800, pmi011900, pmi020100, pmi020101, pmi020102, pmi020200, pmi020201, pmi020202, pmi020300, pmi020301, pmi020302, pmi020400, pmi020401, pmi020402, pmi020500, pmi020501, pmi020502, pmi020600, pmi020601, pmi020602, pmi020700, pmi020800, pmi020900, pmi021000, pmi030000 |
| `top_list` | `stock_top_list` | date | ok | 79 | trade_date, ts_code, name, close, pct_change, turnover_rate, amount, l_sell, l_buy, l_amount, net_amount, net_rate, amount_rate, float_values, reason |
| `top_inst` | `stock_top_inst` | date | ok | 790 | trade_date, ts_code, exalter, buy, buy_rate, sell, sell_rate, net_buy, side, reason |
| `cyq_perf` | `stock_cyq_perf` | date | ok | 5573 | ts_code, trade_date, his_low, his_high, cost_5pct, cost_15pct, cost_50pct, cost_85pct, cost_95pct, weight_avg, winner_rate |
| `ths_index` | `index_ths` | catalog | ok | 1666 | ts_code, name, count, exchange, list_date, type |
| `ths_daily` | `index_ths_daily` | date | ok | 1874 | ts_code, trade_date, open, high, low, close, pre_close, avg_price, change, pct_change, vol, turnover_rate |
| `ths_member` | `index_ths_member` | custom | ok | 320 | ts_code, con_code, con_name |
| `moneyflow_dc` | `stock_moneyflow_ext` | date | ok | 6032 | trade_date, ts_code, name, pct_change, close, net_amount, net_amount_rate, buy_elg_amount, buy_elg_amount_rate, buy_lg_amount, buy_lg_amount_rate, buy_md_amount, buy_md_amount_rate, buy_sm_amount, buy_sm_amount_rate |
| `moneyflow_ths` | `stock_moneyflow_ext` | date | ok | 5212 | trade_date, ts_code, name, pct_change, latest, net_amount, net_d5_amount, buy_lg_amount, buy_lg_amount_rate, buy_md_amount, buy_md_amount_rate, buy_sm_amount, buy_sm_amount_rate |
| `moneyflow_ind_dc` | `stock_moneyflow_ind` | date | ok | 1058 | trade_date, content_type, ts_code, name, pct_change, close, net_amount, net_amount_rate, buy_elg_amount, buy_elg_amount_rate, buy_lg_amount, buy_lg_amount_rate, buy_md_amount, buy_md_amount_rate, buy_sm_amount, buy_sm_amount_rate, buy_sm_amount_stock, rank |
| `moneyflow_ind_ths` | `stock_moneyflow_ind` | date | ok | 90 | trade_date, ts_code, industry, lead_stock, close, pct_change, company_num, pct_change_stock, close_price, net_buy_amount, net_sell_amount, net_amount |
| `moneyflow_cnt_ths` | `stock_moneyflow_ind` | date | ok | 386 | trade_date, ts_code, name, lead_stock, close_price, pct_change, industry_index, company_num, pct_change_stock, net_buy_amount, net_sell_amount, net_amount |
| `daily_info` | `market_daily_info` | date | ok | 12 | trade_date, ts_code, ts_name, com_count, total_share, float_share, total_mv, float_mv, amount, vol, trans_count, pe, tr, exchange |
| `sz_daily_info` | `market_daily_info` | date | ok | 14 | trade_date, ts_code, count, amount, vol, total_share, total_mv, float_share, float_mv |
| `block_trade` | `stock_block_trade` | date | ok | 49 | ts_code, trade_date, price, vol, amount, buyer, seller |
| `index_global` | `index_global_daily` | date | ok | 21 | ts_code, trade_date, open, close, high, low, pre_close, change, pct_chg, swing, vol |
| `fut_basic` | `fut_basic` | catalog | ok | 696 | ts_code, symbol, exchange, name, fut_code, multiplier, trade_unit, per_unit, quote_unit, quote_unit_desc, d_mode_desc, list_date, delist_date, d_month, last_ddate |
| `fut_daily` | `fut_daily` | date | ok | 1076 | ts_code, trade_date, pre_close, pre_settle, open, high, low, close, settle, change1, change2, vol, amount, oi, oi_chg |
| `fut_holding` | `fut_holding` | date | ok | 2 | trade_date, symbol, broker, vol, vol_chg, long_hld, long_chg, short_hld, short_chg |
| `fut_wsr` | `fut_wsr` | date | ok | 42 | trade_date, symbol, fut_name, warehouse, pre_vol, vol, vol_chg, unit |
| `fut_settle` | `fut_settle` | date | ok | 898 | ts_code, trade_date, settle, trading_fee_rate, trading_fee, delivery_fee, b_hedging_margin_rate, s_hedging_margin_rate, long_margin_rate, short_margin_rate |
| `fut_mapping` | `fut_mapping` | date | ok | 202 | ts_code, trade_date, mapping_ts_code |
| `fut_index_daily` | `fut_index_daily` | custom | ok | 5062 | ts_code, trade_date, close, open, high, low, pre_close, change, pct_chg, vol, amount |
| `opt_basic` | `opt_basic` | catalog | ok | 12000 | ts_code, symbol, exchange, name, per_unit, opt_code, opt_type, call_put, exercise_type, exercise_price, opt_multiplier, s_month, maturity_date, list_price, list_date, delist_date, last_edate, last_ddate, quote_unit, min_price_chg |
| `opt_daily` | `opt_daily` | date | ok | 15000 | ts_code, trade_date, exchange, pre_settle, pre_close, open, high, low, close, settle, vol, amount, oi |
| `cb_basic` | `cb_basic` | catalog | ok | 1179 | ts_code, bond_full_name, bond_short_name, cb_type, cb_code, stk_code, stk_short_name, maturity, par, issue_price, issue_size, remain_size, value_date, maturity_date, rate_type, coupon_rate, add_rate, pay_per_year, list_date, delist_date, exchange, conv_start_date, conv_end_date, conv_stop_date, first_conv_price, conv_price, rate_clause |
| `cb_issue` | `cb_issue` | range | ok | 17 | ts_code, ann_date, res_ann_date, plan_issue_size, issue_size, issue_price, issue_type, onl_code, onl_name, onl_date, onl_size, onl_pch_vol, onl_pch_num, onl_pch_excess, shd_ration_code, shd_ration_name, shd_ration_date, shd_ration_record_date, shd_ration_pay_date, shd_ration_price, shd_ration_ratio, shd_ration_size, offl_size |
| `cb_call` | `cb_call` | range | ok | 52 | ts_code, call_type, is_call, ann_date, call_date, call_price, call_price_tax, call_vol, call_amount, payment_date, call_reg_date |
| `cb_daily` | `cb_daily` | date | ok | 315 | ts_code, trade_date, pre_close, open, high, low, close, change, pct_chg, vol, amount |
| `cb_share` | `cb_share` | custom | ok | 2000 | ts_code, bond_short_name, publish_date, end_date, issue_size, convert_price_initial, convert_price, convert_val, convert_vol, convert_ratio, acc_convert_val, acc_convert_vol, acc_convert_ratio, remain_size, total_shares |
| `cb_rating` | `cb_rating` | custom | ok | 6 | ts_code, ann_date, rating_date, rating_com_name, rating_way, rating_type, rating, rating_outlook |
| `hsgt_top10` | `stock_hsgt_top10` | date | ok | 10 | trade_date, ts_code, name, close, change, rank, market_type, amount, net_amount, buy, sell |
| `pledge_detail` | `stock_pledge_detail` | range | ok | 1500 | ts_code, ann_date, holder_name, pledge_amount, start_date, end_date, is_release, release_date, pledgor, holding_amount, pledged_amount, p_total_ratio, h_total_ratio, is_buyback |
| `repurchase` | `stock_repurchase` | range | ok | 1878 | ts_code, ann_date, end_date, proc, exp_date, vol, amount, high_limit, low_limit |
| `stk_surv` | `stock_surv` | range | ok | 400 | ts_code, name, surv_date, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece |
| `kpl_list` | `stock_kpl_list` | date | ok | 33 | ts_code, name, trade_date, lu_time, ld_time, open_time, last_time, lu_desc, tag, theme, net_change, bid_amount, status, bid_change, bid_turnover, lu_bid_vol, pct_chg, bid_pct_chg, rt_pct_chg, limit_order, amount, turnover_rate, free_float, lu_limit_order |
| `hm_list` | `stock_hm_list` | catalog | ok | 121 | name, desc, orgs |
| `eco_cal` | `macro_eco_cal` | range | ok | 100 | date, time, currency, country, event, value, pre_value, fore_value |
| `hk_basic` | `hk_basic` | catalog | ok | 2781 | ts_code, name, fullname, enname, cn_spell, market, list_status, list_date, delist_date, trade_unit, isin, curr_type |
| `hk_daily` | `hk_daily` | date | ok(首次) | 2210 | ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount |
| `us_basic` | `us_basic` | catalog | ok | 6000 | ts_code, name, enname, classify, list_date, delist_date |
| `us_daily` | `us_daily` | date | ok(首次) | 8000 | ts_code, trade_date, close, open, high, low, pre_close, pct_change, vol, amount, vwap |
| `ggt_daily` | `ggt_daily` | date | ok | 1 | trade_date, buy_amount, buy_volume, sell_amount, sell_volume |

## 缺口与错误

- `hk_daily` / `us_daily`：**首次探针（15:50）成功**（hk_daily 2,210 行、us_daily 8,000 行），
  上表字段取自首次返回；复跑触发接口限流（错误原文「频率超限(1次/小时)」，见
  `assets/_probe_retry.md`）。二者当前无权限缺口，最终干净复跑需等 1 小时窗口。
- 其余 62 个接口本次全部 `ok`，无权限缺口。
