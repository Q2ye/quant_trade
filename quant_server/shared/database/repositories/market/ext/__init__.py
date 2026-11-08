# -*- coding: utf-8 -*-
"""日频数据底座仓储包（一表一 Repository 类）。"""

from .events_repo import (
    MacroEcoCalRepository,
    StockHmListRepository,
    StockKplListRepository,
    StockPledgeDetailRepository,
    StockRepurchaseRepository,
    StockSurvRepository,
)
from .flow_ths_repo import (
    IndexThsDailyRepository,
    IndexThsMemberRepository,
    IndexThsRepository,
    MarketDailyInfoRepository,
    StockCyqPerfRepository,
    StockMoneyflowExtRepository,
    StockMoneyflowIndRepository,
    StockTopInstRepository,
    StockTopListRepository,
)
from .futures_repo import (
    FutBasicRepository,
    FutDailyRepository,
    FutHoldingRepository,
    FutIndexDailyRepository,
    FutMappingRepository,
    FutSettleRepository,
    FutWsrRepository,
    IndexGlobalDailyRepository,
    StockBlockTradeRepository,
)
from .fx_fund_repo import (
    FundBasicRepository,
    FundCompanyRepository,
    FundDailyExRepository,
    FundDivRepository,
    FundManagerRepository,
    FundNavRepository,
    FundShareRepository,
    FxBasicRepository,
    FxDailyRepository,
)
from .margin_macro_repo import (
    IndexMonthlyRepository,
    MacroMoneyRepository,
    MacroPmiRepository,
    MacroRateRepository,
    MacroSfRepository,
    StockMarginDetailRepository,
    StockMarginSecsRepository,
    StockNamechangeRepository,
    StockNewShareRepository,
)
from .options_bonds_repo import (
    CbBasicRepository,
    CbCallRepository,
    CbDailyRepository,
    CbIssueRepository,
    CbRatingRepository,
    CbShareRepository,
    OptBasicRepository,
    OptDailyRepository,
    StockHsgtTop10Repository,
)
from .overseas_repo import (
    GgtDailyRepository,
    HkBasicRepository,
    HkDailyRepository,
    UsBasicRepository,
    UsDailyRepository,
)
from .progress_repo import DataBackfillProgressRepository

REPO_CLASSES = (
    FxBasicRepository, FxDailyRepository, FundNavRepository, FundBasicRepository,
    FundCompanyRepository, FundManagerRepository, FundDivRepository,
    FundShareRepository, FundDailyExRepository,
    StockMarginDetailRepository, StockMarginSecsRepository,
    StockNamechangeRepository, StockNewShareRepository, IndexMonthlyRepository,
    MacroRateRepository, MacroSfRepository, MacroMoneyRepository,
    MacroPmiRepository,
    StockTopListRepository, StockTopInstRepository, StockCyqPerfRepository,
    IndexThsRepository, IndexThsDailyRepository, IndexThsMemberRepository,
    StockMoneyflowExtRepository, StockMoneyflowIndRepository,
    MarketDailyInfoRepository,
    StockBlockTradeRepository, IndexGlobalDailyRepository, FutBasicRepository,
    FutDailyRepository, FutHoldingRepository, FutWsrRepository,
    FutSettleRepository, FutMappingRepository, FutIndexDailyRepository,
    OptBasicRepository, OptDailyRepository, CbBasicRepository, CbIssueRepository,
    CbCallRepository, CbDailyRepository, CbShareRepository, CbRatingRepository,
    StockHsgtTop10Repository,
    StockPledgeDetailRepository, StockRepurchaseRepository, StockSurvRepository,
    StockKplListRepository, StockHmListRepository, MacroEcoCalRepository,
    HkBasicRepository, HkDailyRepository, UsBasicRepository, UsDailyRepository,
    GgtDailyRepository,
    DataBackfillProgressRepository,
)

REPO_BY_TABLE = {r(None).model.__tablename__: r for r in REPO_CLASSES}

__all__ = ["REPO_CLASSES", "REPO_BY_TABLE"] + [r.__name__ for r in REPO_CLASSES]
