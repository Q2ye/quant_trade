# etf_basic_service.py (completed)
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.data_models import EtfBasic


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

    def batch_create(self, data_list: list) -> list:
        """批量创建ETF记录"""
        if not data_list:
            return []

        results = []
        with self.session_scope() as session:
            for data in data_list:
                try:
                    # 检查是否已存在相同记录
                    existing = session.query(EtfBasic).filter_by(
                        ts_code=data.get('ts_code')
                    ).first()

                    if existing:
                        # 更新现有记录
                        for key, value in data.items():
                            setattr(existing, key, value)
                        results.append(existing)
                    else:
                        # 创建新记录
                        etf = EtfBasic(**data)
                        session.add(etf)
                        results.append(etf)
                except Exception as e:
                    # 记录错误但继续处理其他数据
                    print(f"创建ETF记录失败: {e}, 数据: {data}")
                    continue

            session.flush()
        return results