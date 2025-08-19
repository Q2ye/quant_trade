# stock_moneyflow_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import desc, cast, String
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockMoneyflow


class StockMoneyflowService(BaseService):
    """资金流向服务"""

    def create(self, data: Dict[str, Any]) -> StockMoneyflow:
        """创建新资金流向记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(StockMoneyflow).filter_by(
                ts_code=data['ts_code'],
                trade_date=data['trade_date']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            flow = StockMoneyflow(**data)
            session.add(flow)
            session.flush()
            return flow

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[StockMoneyflow]:
        """批量创建资金流向记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(StockMoneyflow).filter_by(
                    ts_code=data['ts_code'],
                    trade_date=data['trade_date']
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    flow = StockMoneyflow(**data)
                    session.add(flow)
                    results.append(flow)
            session.flush()
        return results

    def get(self, id: int) -> Optional[StockMoneyflow]:
        """根据ID获取资金流向记录"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).get(id)

    def update(self, id: int, update_data: Dict[str, Any]) -> Optional[StockMoneyflow]:
        """更新资金流向记录"""
        with self.session_scope() as session:
            flow = session.query(StockMoneyflow).get(id)
            if flow:
                for key, value in update_data.items():
                    setattr(flow, key, value)
                return flow
            return None

    def delete(self, id: int) -> bool:
        """删除资金流向记录"""
        with self.session_scope() as session:
            flow = session.query(StockMoneyflow).get(id)
            if flow:
                session.delete(flow)
                return True
            return False

    def filter(self, **filters) -> List[StockMoneyflow]:
        """根据条件过滤资金流向记录"""
        with self.session_scope() as session:
            query = session.query(StockMoneyflow)
            for key, value in filters.items():
                query = query.filter(getattr(StockMoneyflow, key) == value)
            return query.all()

    def get_all(self) -> List[StockMoneyflow]:
        """获取所有资金流向记录"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).all()

    def get_by_code_and_date(self, ts_code: str, trade_date: datetime) -> Optional[StockMoneyflow]:
        """根据股票代码和日期获取资金流向"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter_by(
                ts_code=ts_code,
                trade_date=trade_date
            ).first()

    def get_large_net_inflow(self, date: datetime, threshold: float = 1000000) -> List[StockMoneyflow]:
        """获取当日大单净流入超过阈值的股票"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == date,
                StockMoneyflow.net_mf_amount > threshold
            ).order_by(desc(StockMoneyflow.net_mf_amount)).all()

    def get_consecutive_inflow(self, ts_code: str, days: int = 3) -> List[StockMoneyflow]:
        """检测连续资金净流入"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.ts_code == ts_code,
                StockMoneyflow.net_mf_amount > 0
            ).order_by(desc(StockMoneyflow.trade_date)).limit(days).all()

    def get_top_inflow_stocks(self, trade_date: datetime, limit: int = 10) -> List[StockMoneyflow]:
        """获取当日资金净流入最多的股票"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).order_by(desc(StockMoneyflow.net_mf_amount)).limit(limit).all()

    def get_top_outflow_stocks(self, trade_date: datetime, limit: int = 10) -> List[StockMoneyflow]:
        """获取当日资金净流出最多的股票"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).order_by(StockMoneyflow.net_mf_amount).limit(limit).all()

    def get_main_force_inflow(self, trade_date: datetime, limit: int = 10) -> List[StockMoneyflow]:
        """获取当日主力资金流入最多的股票"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).order_by(desc(
                StockMoneyflow.buy_elg_amount + StockMoneyflow.buy_lg_amount
            )).limit(limit).all()

    def get_main_force_outflow(self, trade_date: datetime, limit: int = 10) -> List[StockMoneyflow]:
        """获取当日主力资金流出最多的股票"""
        with self.session_scope() as session:
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).order_by(desc(
                StockMoneyflow.sell_elg_amount + StockMoneyflow.sell_lg_amount
            )).limit(limit).all()

    def get_retail_inflow_ratio(self, trade_date: datetime, limit: int = 10) -> List[StockMoneyflow]:
        """获取当日散户资金流入比例最高的股票"""
        with self.session_scope() as session:
            inflow_ratio = (
                ((StockMoneyflow.buy_sm_amount + StockMoneyflow.buy_md_amount) /
                (StockMoneyflow.buy_sm_amount + StockMoneyflow.buy_md_amount +
                 StockMoneyflow.buy_lg_amount + StockMoneyflow.buy_elg_amount) * 100)
            )
            inflow_ratio_str = cast(inflow_ratio, String)
            return session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).order_by(desc(inflow_ratio_str)).limit(limit).all()

    def analyze_moneyflow_trend(self, ts_code: str, days: int = 30) -> Dict[str, Any]:
        """分析资金流向趋势"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        with self.session_scope() as session:
            data = session.query(StockMoneyflow).filter(
                StockMoneyflow.ts_code == ts_code,
                StockMoneyflow.trade_date >= start_date,
                StockMoneyflow.trade_date <= end_date
            ).order_by(StockMoneyflow.trade_date).all()

            if not data:
                return {}

            net_amounts = [d.net_mf_amount for d in data]
            main_force_in = [d.buy_elg_amount + d.buy_lg_amount for d in data]
            main_force_out = [d.sell_elg_amount + d.sell_lg_amount for d in data]
            retail_in = [d.buy_sm_amount + d.buy_md_amount for d in data]
            retail_out = [d.sell_sm_amount + d.sell_md_amount for d in data]

            return {
                'total_net_inflow': sum(net_amounts),
                'avg_daily_net_inflow': sum(net_amounts) / len(net_amounts),
                'main_force_net_inflow': sum(main_force_in) - sum(main_force_out),
                'retail_net_inflow': sum(retail_in) - sum(retail_out),
                'consecutive_inflow_days': len([x for x in net_amounts if x > 0]),
                'consecutive_outflow_days': len([x for x in net_amounts if x < 0]),
                'max_single_day_inflow': max(net_amounts) if net_amounts else 0,
                'max_single_day_outflow': min(net_amounts) if net_amounts else 0
            }

    def detect_abnormal_moneyflow(self, trade_date: datetime, threshold: float = 3.0) -> List[Dict[str, Any]]:
        """检测异常资金流向"""
        with self.session_scope() as session:
            # 获取当日所有资金流向数据
            daily_data = session.query(StockMoneyflow).filter(
                StockMoneyflow.trade_date == trade_date
            ).all()

            if not daily_data:
                return []

            # 计算平均值和标准差
            net_amounts = [d.net_mf_amount for d in daily_data]
            avg_net = sum(net_amounts) / len(net_amounts)
            std_net = (sum((x - avg_net) ** 2 for x in net_amounts) / len(net_amounts)) ** 0.5

            # 检测异常值
            abnormal = []
            for data in daily_data:
                z_score = (data.net_mf_amount - avg_net) / std_net if std_net else 0
                if abs(z_score) > threshold:
                    abnormal.append({
                        'ts_code': data.ts_code,
                        'net_mf_amount': data.net_mf_amount,
                        'z_score': z_score,
                        'main_force_net': data.buy_elg_amount + data.buy_lg_amount -
                                          data.sell_elg_amount - data.sell_lg_amount,
                        'retail_net': data.buy_sm_amount + data.buy_md_amount -
                                      data.sell_sm_amount - data.sell_md_amount
                    })

            return abnormal