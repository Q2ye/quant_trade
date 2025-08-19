# etf_basic_service.py (completed)
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import EtfBasic


class EtfBasicService(BaseService):
    """ETF基础信息服务"""

    def create(self, data: dict):
        """创建新ETF记录"""
        with self.session_scope() as session:
            etf = EtfBasic(**data)
            session.add(etf)
            session.flush()
            return etf

    def get(self, ts_code: str):
        """根据代码获取ETF信息"""
        with self.session_scope() as session:
            return session.query(EtfBasic).get(ts_code)

    def update(self, ts_code: str, update_data: dict):
        """更新ETF信息"""
        with self.session_scope() as session:
            etf = session.query(EtfBasic).get(ts_code)
            if etf:
                for key, value in update_data.items():
                    setattr(etf, key, value)
            return etf

    def delete(self, ts_code: str):
        """删除ETF记录"""
        with self.session_scope() as session:
            etf = session.query(EtfBasic).get(ts_code)
            if etf:
                session.delete(etf)

    def filter(self, **filters):
        """根据条件过滤ETF记录"""
        with self.session_scope() as session:
            return session.query(EtfBasic).filter_by(**filters).all()

    def get_all(self):
        """获取所有ETF记录"""
        with self.session_scope() as session:
            return session.query(EtfBasic).all()

    def get_by_index(self, index_code: str):
        """获取跟踪特定指数的ETF"""
        with self.session_scope() as session:
            return session.query(EtfBasic).filter_by(index_code=index_code).all()

    def get_by_asset_class(self, asset_class: str):
        """按资产类别获取ETF"""
        with self.session_scope() as session:
            return session.query(EtfBasic).filter_by(etf_type=asset_class).all()

    def get_by_exchange(self, exchange: str):
        """按交易所获取ETF"""
        with self.session_scope() as session:
            return session.query(EtfBasic).filter_by(exchange=exchange).all()