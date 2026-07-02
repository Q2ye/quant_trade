# -*- coding: utf-8 -*-
"""
申万一级行业 → 板块分组映射

用途：行业轮动策略板块去重——同一板块最多持仓 N 个行业，防止假分散。

申万行业分类版本：2021 版（31 个一级行业）
数据来源：index_sw_classify + index_sw_daily 最新 name 字段
最后更新：2026-07-02
"""

from typing import Dict, List

# ---- 行业名 → 板块名 ----
INDUSTRY_TO_SECTOR: Dict[str, str] = {
    # 金融（银行+非银+地产 → 三大金融属性行业）
    "银行": "金融",
    "非银金融": "金融",
    "房地产": "金融",

    # 周期（上游资源品）
    "有色金属": "周期",
    "煤炭": "周期",
    "钢铁": "周期",
    "石油石化": "周期",
    "基础化工": "周期",

    # 制造（中游制造）
    "电力设备": "制造",
    "机械设备": "制造",
    "汽车": "制造",
    "国防军工": "制造",

    # 消费（下游消费）
    "食品饮料": "消费",
    "家用电器": "消费",
    "纺织服饰": "消费",
    "商贸零售": "消费",
    "社会服务": "消费",
    "美容护理": "消费",

    # 科技（TMT）
    "电子": "科技",
    "计算机": "科技",
    "通信": "科技",
    "传媒": "科技",

    # 医药
    "医药生物": "医药",

    # 公用地产基建
    "公用事业": "公用基建",
    "交通运输": "公用基建",
    "建筑装饰": "公用基建",
    "建筑材料": "公用基建",
    "环保": "公用基建",

    # 农林轻工
    "农林牧渔": "农林轻工",
    "轻工制造": "农林轻工",

    # 综合
    "综合": "综合",
}

# ---- 板块名 → 行业列表 ----
SECTOR_INDUSTRIES: Dict[str, List[str]] = {}
for _industry, _sector in INDUSTRY_TO_SECTOR.items():
    if _sector not in SECTOR_INDUSTRIES:
        SECTOR_INDUSTRIES[_sector] = []
    SECTOR_INDUSTRIES[_sector].append(_industry)

# ---- 板块名列表（按推荐优先级排序） ----
SECTOR_NAMES: List[str] = [
    "金融",
    "周期",
    "制造",
    "科技",
    "消费",
    "医药",
    "公用基建",
    "农林轻工",
    "综合",
]


def get_sector(industry_name: str) -> str:
    """
    获取行业所属板块。

    Args:
        industry_name: 申万行业名（如 "银行"、"医药生物"）

    Returns:
        板块名；未匹配到则返回 "其他"
    """
    return INDUSTRY_TO_SECTOR.get(industry_name, "其他")


def get_industries_in_sector(sector_name: str) -> List[str]:
    """
    获取板块下的所有行业。

    Args:
        sector_name: 板块名

    Returns:
        行业名列表
    """
    return SECTOR_INDUSTRIES.get(sector_name, [])
