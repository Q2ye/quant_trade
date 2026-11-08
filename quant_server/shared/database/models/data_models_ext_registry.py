# -*- coding: utf-8 -*-
"""日频数据底座模型注册表：表名 → 模型类。"""

from .data_models_ext_events import (
    MacroEcoCal,
    StockHmList,
    StockKplList,
    StockPledgeDetail,
    StockRepurchase,
    StockSurv,
)
from .data_models_ext_flow_ths import (
    IndexThs,
    IndexThsDaily,
    IndexThsMember,
    MarketDailyInfo,
    StockCyqPerf,
    StockMoneyflowExt,
    StockMoneyflowInd,
    StockTopInst,
    StockTopList,
)
from .data_models_ext_futures import (
    FutBasic,
    FutDaily,
    FutHolding,
    FutIndexDaily,
    FutMapping,
    FutSettle,
    FutWsr,
    IndexGlobalDaily,
    StockBlockTrade,
)
from .data_models_ext_fx_fund import (
    FundBasic,
    FundCompany,
    FundDailyEx,
    FundDiv,
    FundManager,
    FundNav,
    FundShare,
    FxBasic,
    FxDaily,
)
from .data_models_ext_margin_macro import (
    IndexMonthly,
    MacroMoney,
    MacroPmi,
    MacroRate,
    MacroSf,
    StockMarginDetail,
    StockMarginSecs,
    StockNamechange,
    StockNewShare,
)
from .data_models_ext_options_bonds import (
    CbBasic,
    CbCall,
    CbDaily,
    CbIssue,
    CbRating,
    CbShare,
    OptBasic,
    OptDaily,
    StockHsgtTop10,
)
from .data_models_ext_overseas import GgtDaily, HkBasic, HkDaily, UsBasic, UsDaily
from .data_models_ext_progress import DataBackfillProgress

EXT_MODELS = {
    m.__tablename__: m
    for m in (
        FxBasic, FxDaily, FundNav, FundBasic, FundCompany, FundManager, FundDiv,
        FundShare, FundDailyEx,
        StockMarginDetail, StockMarginSecs, StockNamechange, StockNewShare,
        IndexMonthly, MacroRate, MacroSf, MacroMoney, MacroPmi,
        StockTopList, StockTopInst, StockCyqPerf, IndexThs, IndexThsDaily,
        IndexThsMember, StockMoneyflowExt, StockMoneyflowInd, MarketDailyInfo,
        StockBlockTrade, IndexGlobalDaily, FutBasic, FutDaily, FutHolding, FutWsr,
        FutSettle, FutMapping, FutIndexDaily,
        OptBasic, OptDaily, CbBasic, CbIssue, CbCall, CbDaily, CbShare, CbRating,
        StockHsgtTop10,
        StockPledgeDetail, StockRepurchase, StockSurv, StockKplList, StockHmList,
        MacroEcoCal,
        HkBasic, HkDaily, UsBasic, UsDaily, GgtDaily,
        DataBackfillProgress,
    )
}

__all__ = ["EXT_MODELS"]
