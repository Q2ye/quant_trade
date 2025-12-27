# stock_company_service.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, desc
from ..services.base_service import BaseService
from quant_server.shared.database.models.data_models import StockCompany, StockBasic


class StockCompanyService(BaseService):
    """上市公司信息服务"""

    def create(self, data: Dict[str, Any]) -> StockCompany:
        """创建新公司记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(StockCompany).filter_by(ts_code=data['ts_code']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            company = StockCompany(**data)
            session.add(company)
            session.flush()
            return company

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[StockCompany]:
        """批量创建公司记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(StockCompany).filter_by(ts_code=data['ts_code']).first()
                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    company = StockCompany(**data)
                    session.add(company)
                    results.append(company)
            session.flush()
        return results

    def get(self, ts_code: str) -> Optional[StockCompany]:
        """根据股票代码获取公司信息"""
        with self.session_scope() as session:
            return session.query(StockCompany).filter_by(ts_code=ts_code).first()

    def update(self, ts_code: str, update_data: Dict[str, Any]) -> Optional[StockCompany]:
        """更新公司信息"""
        with self.session_scope() as session:
            company = session.query(StockCompany).filter_by(ts_code=ts_code).first()
            if company:
                for key, value in update_data.items():
                    setattr(company, key, value)
                return company
            return None

    def delete(self, ts_code: str) -> bool:
        """删除公司记录"""
        with self.session_scope() as session:
            company = session.query(StockCompany).filter_by(ts_code=ts_code).first()
            if company:
                session.delete(company)
                return True
            return False

    def filter(self, **filters) -> List[StockCompany]:
        """根据条件过滤公司记录"""
        with self.session_scope() as session:
            query = session.query(StockCompany)
            for key, value in filters.items():
                query = query.filter(getattr(StockCompany, key) == value)
            return query.all()

    def get_all(self) -> List[StockCompany]:
        """获取所有上市公司记录"""
        with self.session_scope() as session:
            return session.query(StockCompany).all()

    def get_by_region(self, province: str, city: str = None) -> List[StockCompany]:
        """根据地区获取公司列表"""
        with self.session_scope() as session:
            query = session.query(StockCompany).filter_by(province=province)
            if city:
                query = query.filter_by(city=city)
            return query.all()

    def get_by_industry(self, industry: str) -> List[StockCompany]:
        """根据行业获取公司列表"""
        # 需要通过StockBasic表关联查询
        with self.session_scope() as session:
            return session.query(StockCompany).join(
                StockBasic, StockCompany.ts_code == StockBasic.ts_code
            ).filter(StockBasic.industry == industry).all()

    def get_companies_by_capital_range(self, min_capital: float, max_capital: float) -> List[StockCompany]:
        """根据注册资本范围获取公司列表"""
        with self.session_scope() as session:
            return session.query(StockCompany).filter(
                and_(
                    StockCompany.reg_capital >= min_capital,
                    StockCompany.reg_capital <= max_capital
                )
            ).all()

    def search_companies(self, keyword: str) -> List[StockCompany]:
        """搜索公司"""
        with self.session_scope() as session:
            return session.query(StockCompany).filter(
                or_(
                    StockCompany.com_name.like(f"%{keyword}%"),
                    StockCompany.main_business.like(f"%{keyword}%"),
                    StockCompany.business_scope.like(f"%{keyword}%")
                )
            ).all()

    def count_by_province(self) -> Dict[str, int]:
        """统计各省份的公司数量"""
        with self.session_scope() as session:
            result = session.query(
                StockCompany.province,
                func.count(StockCompany.ts_code)
            ).group_by(StockCompany.province).all()
            return {province: count for province, count in result if province}

    def count_by_industry(self) -> Dict[str, int]:
        """统计各行业的公司数量"""
        # 需要通过StockBasic表关联查询
        with self.session_scope() as session:
            result = session.query(
                StockBasic.industry,
                func.count(StockCompany.ts_code)
            ).join(
                StockCompany, StockBasic.ts_code == StockCompany.ts_code
            ).group_by(StockBasic.industry).all()
            return {industry: count for industry, count in result if industry}

    def get_companies_with_largest_capital(self, limit: int = 10) -> List[StockCompany]:
        """获取注册资本最大的公司"""
        with self.session_scope() as session:
            return session.query(StockCompany).order_by(
                desc(StockCompany.reg_capital)
            ).limit(limit).all()

    def get_companies_with_most_employees(self, limit: int = 10) -> List[StockCompany]:
        """获取员工人数最多的公司"""
        with self.session_scope() as session:
            return session.query(StockCompany).filter(
                StockCompany.employees.isnot(None)
            ).order_by(
                desc(StockCompany.employees)
            ).limit(limit).all()