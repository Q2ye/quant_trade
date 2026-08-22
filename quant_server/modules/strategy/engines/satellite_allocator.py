# -*- coding: utf-8 -*-
"""
卫星池子仓分配器（阶段 4d）

对应 `docs/00-核心策略体系/多策略整体架构规划.md` §四/§五：
  铁律1：卫星池 = 总资金 25%（独立账户），主/卫星永不互通
  铁律2：单次事件博弈亏损 ≤ 卫星池 40%（事前仓位 ≤60% + 事后 -40% 强制清仓）
  铁律3（2026-08 修订）：卫星池滚动复利 + 规模上限（>总资金 40% 回流主池）

子仓结构：
  进攻型（microcap）  常态持仓：双门控（大盘 BULL + 微盘指数 >MA20）
  事件型（panic）     平时空仓：恐慌信号触发后出击
  联动：微盘门控2 关闭 → 微盘避让空仓 → 恐慌抄底接棒（时间互补）
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SatelliteAllocator:
	"""卫星池子仓分配 — 无状态纯计算，不持有事件引擎引用"""

	DEFAULT_PARAMS: Dict = {
		"satellite_ratio": 0.25,         # 铁律1：卫星池占总资金比例（主 75% / 卫星 25%）
		"microcap_base_ratio": 1.0,      # 平时进攻子仓占卫星池比例（微盘常态满仓）
		"panic_idle_ratio": 0.0,         # 平时事件子仓占卫星池比例（0 = 空仓等待）
		"panic_trigger_ratio": 1.0,      # 恐慌触发时事件子仓出击比例（全仓）
		"reflow_threshold": 0.40,        # 铁律3：卫星池规模上限（占总资金比例，超出回流主池）
		"panic_loss_cap": 0.40,          # 铁律2：单次事件亏损上限（卫星池 40%，事后强制线）
		"panic_pre_position": 0.60,      # 铁律2：事前单笔仓位上限（事件子仓 60%，留现金防连跌停）
	}

	def __init__(self, params: Optional[Dict] = None):
		merged = {**self.DEFAULT_PARAMS, **(params or {})}
		self.satellite_ratio = float(merged["satellite_ratio"])
		self.microcap_base_ratio = float(merged["microcap_base_ratio"])
		self.panic_idle_ratio = float(merged["panic_idle_ratio"])
		self.panic_trigger_ratio = float(merged["panic_trigger_ratio"])
		self.reflow_threshold = float(merged["reflow_threshold"])
		self.panic_loss_cap = float(merged["panic_loss_cap"])
		self.panic_pre_position = float(merged["panic_pre_position"])

	# ------------------------------------------------------------------
	def allocate(self, micro_gate_open: bool, panic_active: bool) -> Dict[str, float]:
		"""子仓资金分配（输出占卫星池比例，总和 ≤1）。

		Args:
			micro_gate_open: 门控2 开启（微盘趋势健康，可持仓）
			panic_active: 恐慌抄底触发中（信号序列内或持仓中）

		Returns:
			{"microcap": w1, "panic": w2} — 进攻/事件子仓占卫星池的比例
		"""
		if panic_active:
			# 事件型出击：恐慌抄底全仓（卫星池）
			# 联动：恐慌期间微盘门控2 通常已关闭 → 微盘避让空仓（时间互补）
			micro_w = self.microcap_base_ratio if micro_gate_open else 0.0
			return {"microcap": round(micro_w, 4), "panic": round(self.panic_trigger_ratio, 4)}
		# 平时：进攻子仓常态，事件空仓（现金/货币基金）
		micro_w = self.microcap_base_ratio if micro_gate_open else 0.0
		return {"microcap": round(micro_w, 4), "panic": round(self.panic_idle_ratio, 4)}

	# ------------------------------------------------------------------
	def check_reflow(self, total_assets: float, satellite_assets: float) -> Dict:
		"""铁律3：卫星池规模 > 总资金 40% → 超出部分回流主池（年度再平衡窗口）。

		Args:
			total_assets: 组合总资产
			satellite_assets: 卫星池当前资产

		Returns:
			{"should_reflow": bool, "amount": float, "ratio": float, "target_ratio": float}
		"""
		if total_assets <= 0 or satellite_assets <= 0:
			return {"should_reflow": False, "amount": 0.0,
			        "ratio": 0.0, "target_ratio": self.reflow_threshold}
		ratio = satellite_assets / total_assets
		if ratio > self.reflow_threshold:
			reflow = satellite_assets - total_assets * self.reflow_threshold
			return {"should_reflow": True, "amount": round(reflow, 2),
			        "ratio": round(ratio, 4), "target_ratio": self.reflow_threshold}
		return {"should_reflow": False, "amount": 0.0,
		        "ratio": round(ratio, 4), "target_ratio": self.reflow_threshold}

	def check_panic_position(self, position_weight: float, satellite_pool_ratio: float = 1.0) -> Dict:
		"""铁律2：事件型子仓单笔仓位校验（事前 ≤60%，防连跌停无法止损）。"""
		effective_cap = self.panic_pre_position * satellite_pool_ratio
		if position_weight > effective_cap:
			return {"ok": False, "reason": f"事件子仓单笔 {position_weight:.0%} > 上限 {effective_cap:.0%}（铁律2）",
			        "cap": effective_cap}
		return {"ok": True, "reason": "通过", "cap": effective_cap}
