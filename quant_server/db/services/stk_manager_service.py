# stk_manager_service.py (completed)
from ..services.base_service import BaseService
from quant_server.shared.database.models.data_models import StkManager


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
        with self.session_scope() as session:
            return session.query(StkManager).get(id)

    def update(self, id: int, update_data: dict):
        """更新管理层信息"""
        with self.session_scope() as session:
            manager = session.query(StkManager).get(id)
            if manager:
                for key, value in update_data.items():
                    setattr(manager, key, value)
            return manager

    def delete(self, id: int):
        """删除管理层记录"""
        with self.session_scope() as session:
            manager = session.query(StkManager).get(id)
            if manager:
                session.delete(manager)

    def filter(self, **filters):
        """根据条件过滤管理层记录"""
        with self.session_scope() as session:
            return session.query(StkManager).filter_by(**filters).all()

    def get_by_company(self, ts_code: str):
        """获取指定公司的所有管理层信息"""
        with self.session_scope() as session:
            return session.query(StkManager).filter_by(ts_code=ts_code).all()

    def get_active_managers(self, ts_code: str):
        """获取公司现任管理层"""
        with self.session_scope() as session:
            return session.query(StkManager).filter(
                StkManager.ts_code == ts_code,
                StkManager.end_date.is_(None)
            ).all()

    def get_by_title(self, ts_code: str, title: str):
        """获取指定职位的管理层"""
        with self.session_scope() as session:
            return session.query(StkManager).filter(
                StkManager.ts_code == ts_code,
                StkManager.title == title
            ).all()

    def get_all(self):
        """获取所有管理层记录"""
        with self.session_scope() as session:
            return session.query(StkManager).all()

    def batch_create(self, data_list: list) -> list:
        """批量创建管理层记录"""
        if not data_list:
            return []

        results = []
        with self.session_scope() as session:
            for data in data_list:
                try:
                    # 检查是否已存在相同记录
                    existing = session.query(StkManager).filter_by(
                        ts_code=data.get('ts_code'),
                        ann_date=data.get('ann_date'),
                        name=data.get('name'),
                        title=data.get('title')
                    ).first()

                    if existing:
                        # 更新现有记录
                        for key, value in data.items():
                            setattr(existing, key, value)
                        results.append(existing)
                    else:
                        # 创建新记录
                        manager = StkManager(**data)
                        session.add(manager)
                        results.append(manager)
                except Exception as e:
                    # 记录错误但继续处理其他数据
                    print(f"创建管理层记录失败: {e}, 数据: {data}")
                    continue

            session.flush()
        return results