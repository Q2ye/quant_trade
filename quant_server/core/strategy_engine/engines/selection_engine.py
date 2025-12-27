# core/engines/selection_engine.py
import logging
from datetime import datetime
from typing import Dict, List, Optional

from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.db import get_db_session
from quant_server.shared.database.models.business_models import Basket, BasketItem
from quant_server.shared.database.models.data_models import StockBasic, StockDaily, StockDailyBasic

logger = logging.getLogger(__name__)


class SelectionEngine:
    """选股引擎 - 负责多因子筛选和股票池管理"""

    def __init__(self, main_engine, event_engine: EventEngine):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.session = get_db_session()
        self.stock_pool = {}

        # 注册事件处理
        event_engine.register("timer", self.process_timer_event)
        event_engine.register("selection_request", self.process_selection_request)

        logger.info("选股引擎初始化完成")

    def process_timer_event(self, event: Event):
        """处理定时事件 - 定期执行选股"""
        # 使用event参数获取时间信息
        event_time = event.data.get('timestamp', datetime.now())

        # 每天收盘后执行选股
        if event_time.hour == 15 and event_time.minute >= 30:  # 收盘后
            self.run_selection()

    def process_selection_request(self, event: Event):
        """处理选股请求事件"""
        config = event.data
        self.run_selection(config)

    def run_selection(self, config: Optional[Dict] = None):
        """执行选股逻辑"""
        logger.info("开始执行选股逻辑")

        # 获取配置参数
        config = config or {}
        factors = config.get('factors', ['value', 'growth', 'quality'])
        max_stocks = config.get('max_stocks', 50)
        basket_id = config.get('basket_id', 'default')

        try:
            # 获取股票列表 - 修复类型问题
            all_stocks = self.session.query(StockBasic).filter(
                StockBasic.list_status == 'L'  # 仅上市股票
            ).all()

            # 计算因子得分
            scored_stocks = []
            for stock in all_stocks:
                try:
                    score = self._calculate_stock_score(str(stock.ts_code), factors)
                    scored_stocks.append((stock.ts_code, score))
                except Exception as e:
                    logger.warning(f"计算股票 {stock.ts_code} 得分失败: {str(e)}")
                    continue

            # 按得分排序
            scored_stocks.sort(key=lambda x: x[1], reverse=True)

            # 选择前N只股票
            selected_stocks = scored_stocks[:max_stocks]

            # 创建或更新股票篮子
            self._update_basket(basket_id, selected_stocks)

            # 发布选股完成事件
            self.event_engine.put(Event("selection_completed", {
                "basket_id": basket_id,
                "selected_stocks": [s[0] for s in selected_stocks],
                "timestamp": datetime.now()
            }))

            logger.info(f"选股完成，篮子 {basket_id} 包含 {len(selected_stocks)} 只股票")

        except Exception as e:
            logger.error(f"选股执行失败: {str(e)}", exc_info=True)

    def _calculate_stock_score(self, ts_code: str, factors: List[str]) -> float:
        """计算股票综合得分"""
        scores = {}
        weights = {
            'value': 0.4,  # 价值因子权重
            'growth': 0.3,  # 成长因子权重
            'quality': 0.3,  # 质量因子权重
        }

        # 获取最新日线数据
        latest_date = self.session.query(StockDaily.trade_date).filter(
            StockDaily.ts_code == ts_code
        ).order_by(StockDaily.trade_date.desc()).first()

        if not latest_date:
            return 0

        # 修复类型问题：确保日期格式正确
        latest_date_obj = latest_date[0]
        if isinstance(latest_date_obj, datetime):
            latest_date_str = latest_date_obj.strftime('%Y-%m-%d')
        else:
            latest_date_str = str(latest_date_obj)

        # 计算各因子得分
        if 'value' in factors:
            scores['value'] = self._calculate_value_factor(ts_code, latest_date_str)

        if 'growth' in factors:
            scores['growth'] = self._calculate_growth_factor(ts_code, latest_date_str)

        if 'quality' in factors:
            scores['quality'] = self._calculate_quality_factor(ts_code, latest_date_str)

        # 计算综合得分
        total_score = 0
        for factor in factors:
            if factor in scores:
                total_score += scores[factor] * weights.get(factor, 0)

        return total_score

    def _calculate_value_factor(self, ts_code: str, trade_date: str) -> float:
        """计算价值因子得分"""
        # 获取估值指标
        basic_data = self.session.query(StockDailyBasic).filter(
            StockDailyBasic.ts_code == ts_code,
            StockDailyBasic.trade_date == trade_date
        ).first()

        if not basic_data:
            return 0

        # 简化实现：使用PE、PB、PS的倒数作为价值指标
        value_metrics = []

        if basic_data.pe and basic_data.pe > 0:
            value_metrics.append(1 / basic_data.pe)

        if basic_data.pb and basic_data.pb > 0:
            value_metrics.append(1 / basic_data.pb)

        if basic_data.ps and basic_data.ps > 0:
            value_metrics.append(1 / basic_data.ps)

        if not value_metrics:
            return 0

        # 归一化处理
        return sum(value_metrics) / len(value_metrics)

    def _calculate_growth_factor(self, ts_code: str, trade_date: str) -> float:
        """计算成长因子得分"""
        # 获取最近两个季度的数据计算增长率
        # 简化实现：使用价格增长率
        price_data = self.session.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date <= trade_date
        ).order_by(StockDaily.trade_date.desc()).limit(60).all()

        if len(price_data) < 20:
            return 0

        # 计算20日和60日收益率
        returns_20d = price_data[0].close / price_data[19].close - 1
        returns_60d = price_data[0].close / price_data[59].close - 1

        # 综合成长得分
        growth_score = (returns_20d + returns_60d) / 2

        return max(0, int(growth_score))  # 负增长得0分

    def _calculate_quality_factor(self, ts_code: str, trade_date: str) -> float:
        """计算质量因子得分"""
        # 简化实现：使用ROE和利润率作为质量指标
        basic_data = self.session.query(StockDailyBasic).filter(
            StockDailyBasic.ts_code == ts_code,
            StockDailyBasic.trade_date == trade_date
        ).first()

        if not basic_data:
            return 0

        quality_metrics = []

        # 使用ROE（如果有）
        # 使用换手率（低换手率可能表示质量好）
        if basic_data.turnover_rate:
            # 换手率越低，质量得分越高（反转）
            quality_metrics.append(1 - min(1, int(basic_data.turnover_rate / 0.1)))

        return sum(quality_metrics) / len(quality_metrics) if quality_metrics else 0

    def _update_basket(self, basket_id: str, selected_stocks: List[tuple]):
        """更新股票篮子"""
        # 查找或创建篮子
        basket = self.session.query(Basket).filter(Basket.id == basket_id).first()
        if not basket:
            basket = Basket(id=basket_id, name=f"选股篮子_{basket_id}")
            self.session.add(basket)

        # 清空现有成分
        self.session.query(BasketItem).filter(BasketItem.basket_id == basket_id).delete()

        # 添加新成分
        total_score = sum(score for _, score in selected_stocks)
        for i, (ts_code, score) in enumerate(selected_stocks):
            weight = score / total_score if total_score > 0 else 1 / len(selected_stocks)

            item = BasketItem(
                basket_id=basket_id,
                ts_code=ts_code,
                weight=float(weight),
                # 添加rank字段
                created_at=datetime.now()
            )
            self.session.add(item)

        # 更新篮子时间
        basket.updated_at = datetime.now()

        # 提交更改
        self.session.commit()

        logger.info(f"篮子 {basket_id} 更新完成，包含 {len(selected_stocks)} 只股票")