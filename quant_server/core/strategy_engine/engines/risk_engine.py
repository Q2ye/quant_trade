# core/engines/risk_engine.py
import logging
from typing import Dict
from datetime import datetime

from quant_server.core.data_models import PositionData, OrderData, TickData, Direction
from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.db import get_db_session
from quant_server.db.models.business_models import RiskRule, RiskEvent

logger = logging.getLogger(__name__)


class RiskEngine:
    """风控引擎 - 负责实时风险监控和预警"""

    # 默认风控规则
    DEFAULT_RULES = {
        "max_position_ratio": 0.2,  # 单股仓位上限20%
        "max_daily_loss": 0.05,  # 单日亏损上限5%
        "blacklist": []  # 黑名单股票
    }

    def __init__(self, main_engine, event_engine: EventEngine):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.risk_rules = self.DEFAULT_RULES.copy()
        self.session = get_db_session()

        # 从数据库加载风控规则
        self._load_rules_from_db()

        # 当日亏损记录
        self.daily_pnl = 0
        self.daily_high_watermark = 0

        # 注册事件处理
        event_engine.register("position", self.process_position_update)
        event_engine.register("order", self.process_order_event)
        event_engine.register("tick", self.process_tick_event)
        event_engine.register("trade", self.process_trade_event)
        event_engine.register("timer", self.process_timer_event)  # 定时检查

        logger.info("风控引擎初始化完成")

    def _load_rules_from_db(self):
        """从数据库加载风控规则"""
        try:
            db_rules = self.session.query(RiskRule).filter(RiskRule.is_active == True).all()
            for rule in db_rules:
                condition_value = getattr(rule, 'condition', rule.condition)
                self.risk_rules[str(rule.rule_type)] = condition_value

            logger.info(f"从数据库加载 {len(db_rules)} 条风控规则")
        except Exception as e:
            logger.error(f"加载风控规则失败: {str(e)}")

    def process_position_update(self, event: Event):
        """处理持仓更新事件 - 检查仓位限制"""
        position: PositionData = event.data

        # 计算持仓的市场价值（使用当前价格）
        current_price = self._get_current_price(position.symbol)
        market_value = position.volume * current_price if current_price else 0

        # 检查单股仓位限制
        if self.main_engine.total_asset > 0:
            position_ratio = market_value / self.main_engine.total_asset

            # 确保 max_position_ratio 是数字类型
            max_position_ratio = self._get_numeric_rule("max_position_ratio", 0.2)

            if position_ratio > max_position_ratio:
                self._trigger_risk_event(
                    "position_limit",
                    f"股票 {position.symbol} 仓位超过限制: {position_ratio:.2%} > {max_position_ratio:.2%}",
                    {"symbol": position.symbol, "position_ratio": position_ratio}
                )

        # 检查黑名单
        if position.symbol in self.risk_rules["blacklist"]:
            self._trigger_risk_event(
                "blacklist",
                f"持有黑名单股票: {position.symbol}",
                {"symbol": position.symbol}
            )

    def process_order_event(self, event: Event):
        """处理订单事件 - 检查订单风险"""
        order: OrderData = event.data

        # 检查ST股交易
        if self.is_st_stock(order.symbol):
            self._trigger_risk_event(
                "st_stock",
                f"尝试交易ST股票: {order.symbol}",
                {"symbol": order.symbol, "order_id": order.orderid}
            )

        # 检查涨跌停板交易
        if self._is_limit_price(order.symbol, order.price, order.direction):
            self._trigger_risk_event(
                "limit_price",
                f"在涨跌停价格附近交易: {order.symbol} @ {order.price}",
                {"symbol": order.symbol, "price": order.price, "direction": order.direction}
            )

    def process_trade_event(self, event: Event):
        """处理成交事件 - 更新当日盈亏"""
        trade = event.data
        # 更新当日盈亏计算
        # 简化实现：实际应根据持仓成本计算真实盈亏
        self.daily_pnl += trade.volume * trade.price * 0.0002  # 粗略估算手续费和盈亏

        # 检查单日亏损限制
        max_daily_loss = self._get_numeric_rule("max_daily_loss", 0.05)
        loss_limit = self.main_engine.total_asset * max_daily_loss
        if self.daily_pnl < -loss_limit:
            self._trigger_risk_event(
                "daily_loss_limit",
                f"当日亏损超过限制: {self.daily_pnl:.2f} > {loss_limit:.2f}",
                {"daily_pnl": self.daily_pnl, "loss_limit": loss_limit}
            )

    def process_tick_event(self, event: Event):
        """处理Tick事件 - 实时风险监控"""
        tick: TickData = event.data

        # 检查价格异常波动
        if self._is_abnormal_volatility(tick):
            self._trigger_risk_event(
                "abnormal_volatility",
                f"股票 {tick.symbol} 出现异常波动",
                {"symbol": tick.symbol, "price": tick.last_price, "change": tick.last_price / tick.pre_close - 1}
            )

    def process_timer_event(self):
        """定时检查 - 执行周期性风险检查"""
        # 更新当日最高水位线
        if self.main_engine.total_asset > self.daily_high_watermark:
            self.daily_high_watermark = self.main_engine.total_asset

        # 计算当前回撤
        if self.daily_high_watermark > 0:
            drawdown = (self.daily_high_watermark - self.main_engine.total_asset) / self.daily_high_watermark
            if drawdown > 0.08:  # 回撤超过8%
                self._trigger_risk_event(
                    "max_drawdown",
                    f"账户回撤超过阈值: {drawdown:.2%}",
                    {"drawdown": drawdown, "high_watermark": self.daily_high_watermark}
                )

    def _trigger_risk_event(self, event_type: str, message: str, value: Dict):
        """触发风控事件"""
        # 记录到数据库
        risk_event = RiskEvent(
            event_type=event_type,
            event_message=message,
            trigger_value=value,
            created_at=datetime.now()
        )

        try:
            self.session.add(risk_event)
            self.session.commit()
        except Exception as e:
            logger.error(f"记录风控事件失败: {str(e)}")
            self.session.rollback()

        # 发布风控事件
        self.event_engine.put(Event("risk", {
            "type": event_type,
            "message": message,
            "value": value,
            "timestamp": datetime.now()
        }))

        logger.warning(f"风控警报: {message}")

        # 根据事件类型执行相应动作
        if event_type in ["daily_loss_limit", "max_drawdown"]:
            # 停止所有策略
            self.main_engine.stop_all_strategies()

    @staticmethod
    def is_st_stock(symbol: str) -> bool:
        """检查是否为ST股票"""
        # 简化实现：实际应从数据库查询股票ST状态
        return symbol.startswith('ST') or symbol.startswith('*ST')

    def _is_limit_price(self, symbol: str, price: float, direction: Direction) -> bool:
        """检查是否在涨跌停价格附近交易"""
        # 使用参数实现检查逻辑
        # 简化实现：实际应查询股票的涨跌停价格
        # 这里添加一个简单的示例逻辑
        from quant_server.db.models.data_models import StockDailyLimit
        try:
            latest_limit = self.session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == symbol
            ).order_by(StockDailyLimit.trade_date.desc()).first()

            if latest_limit:
                if direction == Direction.BUY and price >= latest_limit.up_limit * 0.99:
                    return True
                elif direction == Direction.SELL and price <= latest_limit.down_limit * 1.01:
                    return True
        except Exception as e:
            logger.error(f"查询涨跌停价格失败: {str(e)}")

        return False

    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        # 实现获取当前价格的逻辑
        # 简化实现：实际应从行情服务获取
        try:
            from quant_server.db.models.data_models import StockDaily
            latest_price = self.session.query(StockDaily.close).filter(
                StockDaily.ts_code == symbol
            ).order_by(StockDaily.trade_date.desc()).first()

            return latest_price[0] if latest_price else 0
        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return 0

    @staticmethod
    def _is_abnormal_volatility(tick: TickData) -> bool:
        """检查是否出现异常波动"""
        # 简化实现：实际应根据历史波动率计算
        if tick.pre_close > 0:
            change = tick.last_price / tick.pre_close - 1
            return abs(change) > 0.07  # 涨跌幅超过7%
        return False

    def _get_numeric_rule(self, rule_name: str, default_value: float) -> float:
        """获取数值类型的规则值"""
        rule_value = self.risk_rules.get(rule_name, default_value)

        # 确保返回的是数值类型
        if isinstance(rule_value, (int, float)):
            return float(rule_value)
        elif isinstance(rule_value, str):
            try:
                return float(rule_value)
            except ValueError:
                logger.warning(f"规则 {rule_name} 的值 '{rule_value}' 无法转换为数字，使用默认值 {default_value}")
                return default_value
        else:
            logger.warning(f"规则 {rule_name} 的值类型不支持，使用默认值 {default_value}")
            return default_value


    def reset_daily_stats(self):
        """重置每日统计（应在每日开盘前调用）"""
        self.daily_pnl = 0
        self.daily_high_watermark = self.main_engine.total_asset