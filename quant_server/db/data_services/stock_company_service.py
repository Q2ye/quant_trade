# stock_company_service.py
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockCompany


class StockCompanyService(BaseService):
    """上市公司信息服务"""

    def create(self, data: dict):
        """创建新公司记录"""
        with self.session_scope() as session:
            company = StockCompany(**data)
            session.add(company)
            session.flush()
            return company

    def get(self, ts_code: str):
        """根据股票代码获取公司信息"""
        return self.filter(StockCompany, ts_code=ts_code).first()

    def update(self, ts_code: str, update_data: dict):
        """更新公司信息"""
        with self.session_scope() as session:
            company = session.query(StockCompany).get(ts_code)
            for key, value in update_data.items():
                setattr(company, key, value)
            return company

    def delete(self, ts_code: str):
        """删除公司记录"""
        with self.session_scope() as session:
            company = session.query(StockCompany).get(ts_code)
            session.delete(company)

    def filter(self, model,**filters):
        """根据条件过滤公司记录"""
        return self.session.query(StockCompany).filter_by(**filters)

    def get_all(self):
        """获取所有上市公司记录"""
        return self.session.query(StockCompany).all()

    def get_by_region(self, province: str, city: str = None):
        """根据地区获取公司列表"""
        query = self.filter(StockCompany,province=province)
        if city:
            query = query.filter_by(city=city)
        return query.all()