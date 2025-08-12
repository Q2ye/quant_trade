# stk_reward_service.py
from sqlalchemy import extract

from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StkReward


class StkRewardService(BaseService):
    """管理层薪酬信息服务"""

    def create(self, data: dict):
        """创建新薪酬记录"""
        with self.session_scope() as session:
            reward = StkReward(**data)
            session.add(reward)
            session.flush()
            return reward

    def get(self, id: int):
        """根据ID获取薪酬信息"""
        return self.filter(id=id).first()

    def update(self, id: int, update_data: dict):
        """更新薪酬信息"""
        with self.session_scope() as session:
            reward = session.query(StkReward).get(id)
            for key, value in update_data.items():
                setattr(reward, key, value)
            return reward

    def delete(self, id: int):
        """删除薪酬记录"""
        with self.session_scope() as session:
            reward = session.query(StkReward).get(id)
            session.delete(reward)

    def filter(self, **filters):
        """根据条件过滤薪酬记录"""
        return self.session.query(StkReward).filter_by(**filters)

    def get_by_manager(self, manager_id: int):
        """获取指定管理层的薪酬记录"""
        return self.filter(manager_id=manager_id).all()

    def get_annual_rewards(self, ts_code: str, year: int):
        """获取公司指定年度的薪酬数据"""
        return self.session.query(StkReward).join(StkManager).filter(
            StkManager.ts_code == ts_code,
            extract('year', StkReward.end_date) == year
        ).all()