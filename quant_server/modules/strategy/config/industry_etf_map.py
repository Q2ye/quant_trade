# -*- coding: utf-8 -*-
"""
申万一级行业 → ETF 映射表

每个行业配置 1-2 只代表性 ETF（primary 优先，secondary 备选）。
ETF 选择标准：
  - 跟踪该行业指数的主流 ETF
  - 日均成交额 > 1000 万元
  - 基金规模 > 2 亿元
  - 管理费率合理（≤ 0.5%）

最后更新：2026-07-02
数据来源：etf_basic + etf_daily 流动性筛选
"""

from typing import Dict, List, Optional

# 行业名 → ETF 映射
# 格式: { 行业名: {"primary": "主ETF代码", "secondary": "备选ETF代码"} }
#
# v2.6 跨行业 ETF 去重规则:
#   当两个行业映射到同一只 primary ETF 时，高排名行业优先使用 primary，
#   低排名行业自动降级到 secondary。若 secondary 也为空或被占用 → 跳过该行业。
#   这可能导致实际持仓 < top_n，但保证了每只 ETF 背后是不同的行业逻辑。
#
# 已知 ETF 共享情况（代码层自动处理，无需手动规避）:
#   159766.SZ ← 商贸零售(primary) > 社会服务(primary) > 美容护理(primary)
#   516160.SH ← 电力设备(primary) > 石油石化(secondary)
#   512200.SH ← 房地产(primary) > 商贸零售(secondary)
#   516950.SH ← 建筑装饰(primary) > 交通运输(secondary)
INDUSTRY_ETF_MAP: Dict[str, Dict[str, str]] = {
    # ---- 金融 ----
    "银行": {
        "primary": "512800.SH",
        "secondary": "515290.SH",
    },
    "非银金融": {
        "primary": "512070.SH",
        "secondary": "512880.SH",  # 证券 ETF（非银主要权重在证券）
    },
    "房地产": {
        "primary": "512200.SH",
        "secondary": "515060.SH",
    },

    # ---- 周期 ----
    "有色金属": {
        "primary": "512400.SH",
        "secondary": "159871.SZ",
    },
    "煤炭": {
        "primary": "515220.SH",
        "secondary": "",
    },
    "钢铁": {
        "primary": "515210.SH",
        "secondary": "",
    },
    "石油石化": {
        "primary": "159697.SZ",  # 石油ETF
        "secondary": "516160.SH",  # 新能源ETF（含石化）
    },
    "基础化工": {
        "primary": "159870.SZ",
        "secondary": "516020.SH",
    },

    # ---- 制造 ----
    "电力设备": {
        "primary": "516160.SH",  # 新能源 ETF（电力设备主要权重）
        "secondary": "159857.SZ",  # 光伏 ETF
    },
    "机械设备": {
        "primary": "159886.SZ",
        "secondary": "516960.SH",
    },
    "汽车": {
        "primary": "516110.SH",
        "secondary": "159889.SZ",
    },
    "国防军工": {
        "primary": "512660.SH",
        "secondary": "512670.SH",
    },

    # ---- 消费 ----
    "食品饮料": {
        "primary": "515170.SH",
        "secondary": "512690.SH",  # 酒 ETF
    },
    "家用电器": {
        "primary": "159996.SZ",
        "secondary": "561120.SH",
    },
    "纺织服饰": {
        "primary": "159850.SZ",  # 消费 ETF（含纺织服饰权重）
        "secondary": "",
    },
    # v2.6: 商贸零售/社会服务/美容护理 共享 159766.SZ
    # 优先级: 商贸零售(primary) > 社会服务(降级) > 美容护理(降级)
    # 商贸零售有 secondary 512200.SH，冲突时可降级
    # 社会服务 & 美容护理 无专属 A 股 ETF，冲突时被跳过（避免假分散）
    "商贸零售": {
        "primary": "159766.SZ",
        "secondary": "512200.SH",
    },
    "社会服务": {
        "primary": "159766.SZ",  # 无专属 ETF，依赖 159766.SZ
        "secondary": "",
    },
    "美容护理": {
        "primary": "159766.SZ",  # 无专属 ETF，依赖 159766.SZ
        "secondary": "",
    },

    # ---- 科技 ----
    "电子": {
        "primary": "159732.SZ",
        "secondary": "512480.SH",  # 半导体 ETF
    },
    "计算机": {
        "primary": "512720.SH",
        "secondary": "159998.SZ",
    },
    "通信": {
        "primary": "515880.SH",
        "secondary": "159994.SZ",
    },
    "传媒": {
        "primary": "512980.SH",
        "secondary": "159805.SZ",
    },

    # ---- 医药 ----
    "医药生物": {
        "primary": "512010.SH",
        "secondary": "159929.SZ",
    },

    # ---- 公用基建 ----
    "公用事业": {
        "primary": "159611.SZ",
        "secondary": "561170.SH",
    },
    "交通运输": {
        "primary": "159662.SZ",
        "secondary": "516950.SH",
    },
    "建筑装饰": {
        "primary": "516950.SH",
        "secondary": "159619.SZ",
    },
    "建筑材料": {
        "primary": "159745.SZ",
        "secondary": "516750.SH",
    },
    "环保": {
        "primary": "159861.SZ",
        "secondary": "512580.SH",
    },

    # ---- 农林轻工 ----
    "农林牧渔": {
        "primary": "159825.SZ",
        "secondary": "159867.SZ",
    },
    "轻工制造": {
        "primary": "159860.SZ",  # 消费 ETF（含轻工制造权重）
        "secondary": "",
    },

    # ---- 综合 ----
    "综合": {
        "primary": "",  # 无专属 ETF，跳过轮动
        "secondary": "",
    },
}

# =============================================================================
# 申万 L1 行业指数代码（v2.5）
#
# 策略需要这些行业指数的日线数据来计算因子评分。
# 代码规则: 801XXX.SI (L1) — 来源: index_sw_daily 表
# =============================================================================
SW_L1_INDUSTRY_CODES: List[str] = [
    "801010.SI",  # 农林牧渔
    "801030.SI",  # 基础化工
    "801040.SI",  # 钢铁
    "801050.SI",  # 有色金属
    "801080.SI",  # 电子
    "801110.SI",  # 家用电器
    "801120.SI",  # 食品饮料
    "801130.SI",  # 纺织服饰
    "801140.SI",  # 轻工制造
    "801150.SI",  # 医药生物
    "801160.SI",  # 公用事业
    "801170.SI",  # 交通运输
    "801180.SI",  # 房地产
    "801200.SI",  # 商贸零售
    "801210.SI",  # 社会服务
    "801230.SI",  # 综合
    "801710.SI",  # 建筑材料
    "801720.SI",  # 建筑装饰
    "801730.SI",  # 电力设备
    "801740.SI",  # 国防军工
    "801750.SI",  # 计算机
    "801760.SI",  # 传媒
    "801770.SI",  # 通信
    "801780.SI",  # 银行
    "801790.SI",  # 非银金融
    "801880.SI",  # 汽车
    "801890.SI",  # 机械设备
    "801950.SI",  # 石油石化
    "801970.SI",  # 环保
    "801980.SI",  # 美容护理
]


def get_etf_for_industry(industry_name: str) -> Optional[str]:
    """
    获取行业对应的主 ETF 代码。

    Args:
        industry_name: 申万行业名

    Returns:
        ETF 代码，如果行业无 ETF 则返回 None
    """
    mapping = INDUSTRY_ETF_MAP.get(industry_name, {})
    return mapping.get("primary") or None


def get_all_etf_codes() -> List[str]:
    """
    获取所有 ETF 候选代码（去重）。

    Returns:
        ETF 代码列表
    """
    codes: set = set()
    for mapping in INDUSTRY_ETF_MAP.values():
        for key in ("primary", "secondary"):
            code = mapping.get(key, "")
            if code:
                codes.add(code)
    return sorted(codes)


def get_industries_with_etf() -> List[str]:
    """
    获取有对应 ETF 的行业列表。

    Returns:
        行业名列表
    """
    return [
        name
        for name, mapping in INDUSTRY_ETF_MAP.items()
        if mapping.get("primary") or mapping.get("secondary")
    ]
