# stk_manager_service.py
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StkManager


class StkManagerService(BaseService):
    """上市公司管理层信息服务"""

    def create(self, data: dict):
        """创建新管理层记录"""
        with self.session_scope() as session:
            manager = StkManager(**data)
            session.add(manager)
            session.flush()
            return manager

    def get(self, id: int):
        """根据ID获取管理层信息"""
        return self.filter(id=id).first()

    def update(self, id: int, update_data: dict):
        """更新管理层信息"""
        with self.session_scope() as session:
            manager = session.query(StkManager).get(id)
            for key, value in update_data.items():
                setattr(manager, key, value)
            return manager

    def delete(self, id: int):
        """删除管理层记录"""
        with self.session_scope() as session:
            manager = session.query(StkManager).get(id)
            session.delete(manager)

    def filter(self, **filters):
        """根据条件过滤管理层记录"""
        return self.session.query(StkManager).filter_by(**filters)

    def get_by_company(self, ts_code: str):
        """获取指定公司的所有管理层信息"""
        return self.filter(ts_code=ts_code).all()

    def get_active_managers(self, ts_code: str):
        """获取公司现任管理层"""
        return self.filter(ts_code=ts_code, end_date=None).all()