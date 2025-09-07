# stk_reward_service.py (completed)
from sqlalchemy import extract

from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import StkReward, StkManager


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
        with self.session_scope() as session:
            return session.query(StkReward).get(id)

    def update(self, id: int, update_data: dict):
        """更新薪酬信息"""
        with self.session_scope() as session:
            reward = session.query(StkReward).get(id)
            if reward:
                for key, value in update_data.items():
                    setattr(reward, key, value)
            return reward

    def delete(self, id: int):
        """删除薪酬记录"""
        with self.session_scope() as session:
            reward = session.query(StkReward).get(id)
            if reward:
                session.delete(reward)

    def filter(self, **filters):
        """根据条件过滤薪酬记录"""
        with self.session_scope() as session:
            return session.query(StkReward).filter_by(**filters).all()

    def get_by_manager(self, manager_id: int):
        """获取指定管理层的薪酬记录"""
        with self.session_scope() as session:
            return session.query(StkReward).filter_by(manager_id=manager_id).all()

    def get_annual_rewards(self, ts_code: str, year: int):
        """获取公司指定年度的薪酬数据"""
        with self.session_scope() as session:
            return session.query(StkReward).join(StkManager).filter(
                StkManager.ts_code == ts_code,
                extract('year', StkReward.end_date) == year
            ).all()

    def get_by_date_range(self, manager_id: int, start_date, end_date):
        """获取指定时间范围的薪酬记录"""
        with self.session_scope() as session:
            return session.query(StkReward).filter(
                StkReward.manager_id == manager_id,
                StkReward.end_date >= start_date,
                StkReward.end_date <= end_date
            ).all()

    def get_all(self):
        """获取所有薪酬记录"""
        with self.session_scope() as session:
            return session.query(StkReward).all()

    def batch_create(self, data_list: list) -> list:
        """批量创建薪酬记录"""
        if not data_list:
            return []

        results = []
        with self.session_scope() as session:
            for data in data_list:
                try:
                    # 检查是否已存在相同记录
                    existing = session.query(StkReward).filter_by(
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
                        reward = StkReward(**data)
                        session.add(reward)
                        results.append(reward)
                except Exception as e:
                    # 记录错误但继续处理其他数据
                    print(f"创建薪酬记录失败: {e}, 数据: {data}")
                    continue

            session.flush()
        return results