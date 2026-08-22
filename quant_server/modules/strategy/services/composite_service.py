# -*- coding: utf-8 -*-
"""
CompositeService — 组合实盘服务

职责:
  - 组合分组 CRUD（composite_groups 表）
  - 组合触发（依次 trigger 各策略 → 信号汇总）
  - Rebalance（CapitalAllocator 计算权重 → 落地 allocated_capital）
"""
import json
import logging
import uuid
from datetime import date, datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.engines.capital_allocator import CapitalAllocator

logger = logging.getLogger(__name__)


class CompositeService:
    """组合实盘服务"""

    def __init__(
        self,
        session: AsyncSession,
        event_engine=None,
        strategy_manager=None,
    ):
        self.session = session
        self.event_engine = event_engine
        self.strategy_manager = strategy_manager

    # =========================================================================
    # 组合分组 CRUD
    # =========================================================================

    async def create_group(self, data: dict, user_id: str) -> dict:
        """创建组合分组"""
        gid = str(uuid.uuid4())
        strategy_ids = []
        for cfg in data.get("strategy_configs", []):
            sid = cfg["strategy_id"]
            aid = cfg.get("allocator_id") or sid
            # 校验策略存在
            stmt = text("SELECT id FROM strategies WHERE id = :sid")
            row = (await self.session.execute(stmt, {"sid": sid})).first()
            if not row:
                raise ValueError(f"策略不存在: {sid}")
            strategy_ids.append({"strategy_id": sid, "allocator_id": aid})

        if len(strategy_ids) < 2:
            raise ValueError("组合至少需要 2 个策略")

        # 2026-08：未传 allocator_config 时按策略角色生成默认（与回测一致：牛市防守让位）。
        # 此前用默认 REGIME_BASE_ALLOCATION(etf_bottom/stock_low_high) 与策略 UUID 不匹配 → 等权 fallback。
        if data.get("allocator_config"):
            allocator_config = data["allocator_config"]
        else:
            allocator_config = await self._default_group_allocator_config(strategy_ids)

        stmt = text("""
            INSERT INTO composite_groups (id, name, account_id, strategy_ids, allocator_config,
                current_regime, status, created_at, updated_at)
            VALUES (:id, :name, :account_id, :strategy_ids, :allocator_config,
                :regime, :status, :now, :now)
        """)
        await self.session.execute(stmt, {
            "id": gid,
            "name": data.get("name", "组合"),
            "account_id": data.get("account_id"),
            "strategy_ids": json.dumps(strategy_ids),
            "allocator_config": json.dumps(allocator_config),
            "regime": 1,
            "status": "active",
            "now": datetime.now(),
        })

        # 反向引用
        for cfg in strategy_ids:
            await self.session.execute(
                text("UPDATE strategies SET composite_group_id = :gid WHERE id = :sid"),
                {"gid": gid, "sid": cfg["strategy_id"]},
            )

        await self.session.commit()
        logger.info(f"创建组合成功: {gid} {data.get('name')}, 策略={strategy_ids}")
        return {"id": gid, "name": data.get("name"), "strategy_ids": strategy_ids}

    async def _default_group_allocator_config(
        self, strategy_ids: list
    ) -> dict:
        """按策略角色生成默认组合分配（与回测一致：牛市防守让位进攻）。

        权重：熊 防守0.9/进攻0.1（进攻熊市空仓）、震 0.2/0.8（进攻动量主场）、牛 0/1。
        key 用 allocator_id（与 CapitalAllocator 查表一致，避免等权 fallback）。
        """
        defense_ids, attack_ids = [], []
        for cfg in strategy_ids:
            if await self._is_defense_strategy(cfg["strategy_id"]):
                defense_ids.append(cfg["allocator_id"])
            else:
                attack_ids.append(cfg["allocator_id"])

        base = {}
        for regime, (d_w, a_w) in ((0, (0.9, 0.1)), (1, (0.2, 0.8)), (2, (0.0, 1.0))):
            alloc = {}
            if defense_ids:
                alloc[defense_ids[0]] = d_w
            if attack_ids:
                alloc[attack_ids[0]] = a_w
            base[regime] = alloc
        return {
            "REGIME_BASE_ALLOCATION": base,
            "risk_parity_enabled": False,
            "rp_blend_strength": 0.3,
            "rp_rebalance_freq": "monthly",
        }

    async def _is_defense_strategy(self, sid: str) -> bool:
        """按策略类名/名称判断是否为防守策略（ETF底部等）。"""
        try:
            stmt = text("SELECT class_name, name FROM strategies WHERE id = :sid")
            row = (await self.session.execute(stmt, {"sid": sid})).first()
            if not row:
                return False
            marker = "{} {}".format(row[0] or "", row[1] or "")
            return any(k in marker for k in ("Bottom", "bottom", "防守", "底部"))
        except Exception:
            return False

    async def get_group(self, group_id: str) -> dict:
        """获取组合详情"""
        stmt = text("SELECT * FROM composite_groups WHERE id = :id")
        row = (await self.session.execute(stmt, {"id": group_id})).first()
        if not row:
            raise ValueError(f"组合不存在: {group_id}")
        return self._row_to_dict(row)

    async def list_groups(self) -> list:
        """列出所有组合"""
        stmt = text("SELECT * FROM composite_groups ORDER BY created_at DESC")
        rows = (await self.session.execute(stmt)).all()
        return [self._row_to_dict(r) for r in rows]

    async def update_group(self, group_id: str, data: dict) -> dict:
        """更新组合"""
        row = (await self.session.execute(
            text("SELECT id FROM composite_groups WHERE id = :id"),
            {"id": group_id}
        )).first()
        if not row:
            raise ValueError(f"组合不存在: {group_id}")

        updates = {"updated_at": datetime.now()}
        if "name" in data:
            updates["name"] = data["name"]
        if "allocator_config" in data:
            updates["allocator_config"] = json.dumps(data["allocator_config"])
        if "strategy_configs" in data:
            updates["strategy_ids"] = json.dumps([
                {"strategy_id": c["strategy_id"], "allocator_id": c.get("allocator_id") or c["strategy_id"]}
                for c in data["strategy_configs"]
            ])

        set_parts = []
        params = {"id": group_id}
        for k, v in updates.items():
            set_parts.append(f"{k} = :{k}")
            params[k] = v

        await self.session.execute(
            text(f"UPDATE composite_groups SET {', '.join(set_parts)} WHERE id = :id"),
            params,
        )
        await self.session.commit()
        return await self.get_group(group_id)

    async def delete_group(self, group_id: str) -> None:
        """删除组合"""
        # 清除反向引用
        await self.session.execute(
            text("UPDATE strategies SET composite_group_id = NULL WHERE composite_group_id = :gid"),
            {"gid": group_id},
        )
        await self.session.execute(
            text("DELETE FROM composite_groups WHERE id = :id"),
            {"id": group_id},
        )
        await self.session.commit()

    # =========================================================================
    # v6.13: 组合成员管理 + 净值查询
    # =========================================================================

    async def add_strategy(self, group_id: str, strategy_id: str,
                           allocator_id: str, w0: float, w1: float, w2: float) -> dict:
        """组合添加策略：加成员 + 权重缩放 + 初始化 allocated_capital。"""
        group = await self.get_group(group_id)
        if group["status"] != "active":
            raise ValueError(f"组合状态异常: {group['status']}")

        strategy_ids = list(group.get("strategy_ids") or [])
        if any(c["strategy_id"] == strategy_id for c in strategy_ids):
            raise ValueError(f"策略 {strategy_id} 已在组合中")

        # 校验策略存在
        row = (await self.session.execute(
            text("SELECT id FROM strategies WHERE id = :sid"), {"sid": strategy_id})).first()
        if not row:
            raise ValueError(f"策略不存在: {strategy_id}")

        aid = allocator_id or strategy_id
        alloc_config = dict(group.get("allocator_config") or {})
        base = dict(alloc_config.get("REGIME_BASE_ALLOCATION") or {})

        # 权重缩放：新权重加入，旧权重按比例缩放，使三档各自总和 = 1
        new_weights = {"0": float(w0), "1": float(w1), "2": float(w2)}
        for regime in ("0", "1", "2"):
            old_map = dict(base.get(regime) or {})
            old_total = sum(float(v) for v in old_map.values())
            nw = new_weights[regime]
            if old_total > 0 and (old_total + nw) > 1.0:
                scale = (1.0 - nw) / old_total
                old_map = {k: round(float(v) * scale, 4) for k, v in old_map.items()}
            old_map[aid] = nw
            base[regime] = old_map
        alloc_config["REGIME_BASE_ALLOCATION"] = base

        strategy_ids.append({"strategy_id": strategy_id, "allocator_id": aid})

        # 更新组合
        await self.session.execute(
            text("""
                UPDATE composite_groups
                SET strategy_ids = :sids, allocator_config = :cfg, updated_at = :now
                WHERE id = :id
            """),
            {"id": group_id, "sids": json.dumps(strategy_ids),
             "cfg": json.dumps(alloc_config), "now": datetime.now()},
        )
        # 策略反向引用
        await self.session.execute(
            text("UPDATE strategies SET composite_group_id = :gid WHERE id = :sid"),
            {"gid": group_id, "sid": strategy_id},
        )
        # 初始化 allocated_capital = 账户余额 × 震荡权重
        account_total = await self._get_account_total(group.get("account_id"))
        init_cap = max(10000.0, account_total * float(w1))
        await self.session.execute(
            text("UPDATE strategies SET allocated_capital = :cap, updated_at = :now WHERE id = :sid"),
            {"cap": init_cap, "now": datetime.now(), "sid": strategy_id},
        )
        await self.session.commit()

        logger.info(f"组合 {group_id} 添加策略 {strategy_id} (allocator={aid}, 权重 {w0}/{w1}/{w2})")
        return {"strategy_id": strategy_id, "allocator_id": aid,
                "weights": {"0": w0, "1": w1, "2": w2}, "initial_capital": init_cap}

    async def remove_strategy(self, group_id: str, strategy_id: str) -> dict:
        """组合移除策略：移除成员 + 移除权重 + 清反向引用。

        移除最后一个策略时，组合无成员 → 自动删除整个组合（复用 delete_group，
        清反向引用 + 删组 + 快照级联删除）。
        """
        group = await self.get_group(group_id)
        strategy_ids = [c for c in group.get("strategy_ids") or [] if c["strategy_id"] != strategy_id]
        if len(strategy_ids) == len(group.get("strategy_ids") or []):
            raise ValueError(f"策略 {strategy_id} 不在组合中")

        # 最后一个策略被移除 → 组合无成员，直接删除整个组合（复用 delete_group）
        if len(strategy_ids) < 1:
            await self.delete_group(group_id)
            logger.info(f"组合 {group_id} 移除最后一个策略 {strategy_id}，组合已删除")
            return {"strategy_id": strategy_id, "composite_deleted": True}

        alloc_config = dict(group.get("allocator_config") or {})
        base = dict(alloc_config.get("REGIME_BASE_ALLOCATION") or {})
        for regime in ("0", "1", "2"):
            m = dict(base.get(regime) or {})
            # 找到该策略的 allocator_id 并移除
            for c in group["strategy_ids"]:
                if c["strategy_id"] == strategy_id:
                    m.pop(c.get("allocator_id"), None)
                    break
            base[regime] = m
        alloc_config["REGIME_BASE_ALLOCATION"] = base

        await self.session.execute(
            text("""
                UPDATE composite_groups
                SET strategy_ids = :sids, allocator_config = :cfg, updated_at = :now
                WHERE id = :id
            """),
            {"id": group_id, "sids": json.dumps(strategy_ids),
             "cfg": json.dumps(alloc_config), "now": datetime.now()},
        )
        await self.session.execute(
            text("UPDATE strategies SET composite_group_id = NULL WHERE id = :sid"),
            {"sid": strategy_id},
        )
        await self.session.commit()
        logger.info(f"组合 {group_id} 移除策略 {strategy_id}")
        return {"strategy_id": strategy_id}

    async def get_nav(self, group_id: str) -> List[Dict]:
        """组合净值序列（composite_account_snapshots）。"""
        stmt = text("""
            SELECT trade_date, total_nav, daily_return, cash, market_value,
                   regime, allocation, per_strategy
            FROM composite_account_snapshots
            WHERE composite_group_id = :gid
            ORDER BY trade_date
        """)
        rows = (await self.session.execute(stmt, {"gid": group_id})).fetchall()
        navs = []
        for r in rows:
            navs.append({
                "trade_date": str(r[0]),
                "total_nav": float(r[1] or 0),
                "daily_return": float(r[2] or 0),
                "cash": float(r[3] or 0),
                "market_value": float(r[4] or 0),
                "regime": int(r[5] or 1),
                "allocation": self._safe_json(r[6]),
                "per_strategy": self._safe_json(r[7]),
            })
        return navs

    # =========================================================================
    # 组合触发
    # =========================================================================

    async def trigger(self, group_id: str, trade_date_str: str,
                      end_date_str: Optional[str] = None,
                      symbols: Optional[List[str]] = None) -> dict:
        """
        组合触发：依次 trigger 组合中所有策略，汇总信号。

        与独立 trigger 的区别：
        - 收集所有策略信号后再统一写入 DB（而非各自 publish）
        - 可选启用信号协调（同标的合并/冲突消解）——P2 实现
        """
        group = await self.get_group(group_id)
        if group["status"] != "active":
            raise ValueError(f"组合状态异常: {group['status']}")

        if not self.strategy_manager:
            raise RuntimeError("StrategyManager 未注入")

        trade_date = date.fromisoformat(trade_date_str)
        end_date = date.fromisoformat(end_date_str) if end_date_str else trade_date

        all_raw_signals = []
        triggered = []
        skipped = []

        for cfg in group["strategy_ids"]:
            sid = cfg["strategy_id"]
            # 检查今天是否已触发
            if await self._was_triggered_today(sid, trade_date_str):
                skipped.append(sid)
                continue

            try:
                result = await self.strategy_manager.trigger_strategy(
                    strategy_id=sid,
                    trade_date=trade_date,
                    end_date=end_date,
                    symbols=symbols,
                )
                if result.get("success") and result.get("data"):
                    sigs = result["data"].get("signals", [])
                    for s in sigs:
                        s["source_strategy_id"] = sid
                    all_raw_signals.extend(sigs)
                triggered.append(sid)
            except Exception as e:
                logger.error(f"组合触发 {sid} 失败: {e}")

        # P2: CompositeSignalCoordinator.process(all_raw_signals) — 信号合并/冲突消解
        # P0: 直接返回原始信号列表

        logger.info(
            f"组合触发完成: {group_id} {trade_date}, "
            f"触发={triggered}, 跳过={skipped}, 信号={len(all_raw_signals)}"
        )

        return {
            "composite_group_id": group_id,
            "trade_date": trade_date_str,
            "regime": group.get("current_regime", 1),
            "allocation": group.get("current_allocation", {}),
            "strategies_triggered": triggered,
            "skipped_strategies": skipped,
            "total_signals": len(all_raw_signals),
            "signals": all_raw_signals,
            "conflicts": [],
        }

    # =========================================================================
    # Rebalance
    # =========================================================================

    async def rebalance(self, group_id: str) -> dict:
        """
        触发 rebalance：与每日自动 rebalance 共用同一实现（_rebalance_one_group）。

        统一两套逻辑（原手动版有独立资本落地/渐进限幅，行为不一致）：
        - regime 用最新 CSI500 判定（不再依赖缓存 current_regime）
        - 写净值快照 + 同步运行中策略 context
        """
        prev_allocation = (await self.get_group(group_id)).get("current_allocation") or {}
        result = await self._rebalance_one_group(group_id)
        return {
            "composite_group_id": group_id,
            "regime": result.get("regime", 1),
            "previous_allocation": prev_allocation,
            "new_allocation": result.get("allocation") or {},
            "capital_changes": result.get("capital_changes", []),
            "account_total": result.get("account_total", 0),
        }

    # =========================================================================
    # v6.13: 组合每日自动 rebalance（共享账户资金池 + CSI500 regime + 同步 context）
    # =========================================================================

    async def run_daily_rebalance(self) -> Dict:
        """对每个活跃组合执行每日 rebalance。"""
        groups = await self.list_groups()
        active = [g for g in groups if g.get("status") == "active"]
        if not active:
            logger.info("无活跃组合，跳过每日 rebalance")
            return {"processed": 0}

        results = []
        for group in active:
            try:
                r = await self._rebalance_one_group(group["id"])
                results.append({"composite_group_id": group["id"], "status": "success", **r})
            except Exception as e:
                logger.error(f"组合 {group['id']} rebalance 失败: {e}", exc_info=True)
                results.append({"composite_group_id": group["id"], "status": "failed", "error": str(e)})

        logger.info(f"组合每日 rebalance 完成: {len(results)} 个组合")
        return {"processed": len(results), "results": results}

    async def _rebalance_one_group(self, group_id: str) -> Dict:
        """单个组合 rebalance：
        1. regime = CSI500 vs MA250 自动判定
        2. CapitalAllocator 权重
        3. 共享账户总资产 × 权重 → 各策略 allocated_capital
        4. 落地 DB + 同步运行中策略 context.initial_capital
        5. 更新组状态 + 写组合净值快照
        """
        from modules.strategy.services.execution_service import ExecutionService

        group = await self.get_group(group_id)
        if group["status"] != "active":
            raise ValueError(f"组合状态异常: {group['status']}")

        # 1. regime 自动判定
        regime = await self._compute_regime()

        # 2. 过滤运行中策略：停止/暂停的策略不参与权重分配，资金及时让给运行中策略
        _sids = [c["strategy_id"] for c in group["strategy_ids"]]
        _status_map = {}
        if _sids:
            _rows = (await self.session.execute(
                text("SELECT id, status FROM strategies WHERE id = ANY(:ids)"),
                {"ids": _sids},
            )).fetchall()
            _status_map = {r[0]: r[1] for r in _rows}
        running_members = [c for c in group["strategy_ids"] if _status_map.get(c["strategy_id"]) == "running"]
        if not running_members:
            logger.info(f"组合 {group_id} 无运行中策略，跳过资金分配")
            return {"regime": regime, "allocation": {}, "account_total": 0.0, "capital_changes": []}

        # 3. 权重（仅运行中策略参与，权重在运行中策略间归一化）
        alloc_config = group.get("allocator_config") or {}
        alloc_ids = [c["allocator_id"] for c in running_members]
        allocator = CapitalAllocator(
            strategy_ids=alloc_ids,
            allocator_params=alloc_config,
            force_regime=regime,
        )
        allocator.rebalance(date.today(), {})
        new_allocation = allocator.allocation

        # 4. 资金池基数 = 共享账户总资产（无则用运行中策略 allocated 之和）
        account_id = group.get("account_id")
        account_total = await self._get_account_total(account_id) if account_id else 0.0
        if account_total <= 0:
            account_total = await self._get_total_allocated(running_members)

        # 5. 落地运行中策略 allocated_capital + 同步 context
        exec_svc = ExecutionService(self.session)
        capital_changes = []
        for cfg in running_members:
            sid = cfg["strategy_id"]
            aid = cfg["allocator_id"]
            weight = new_allocation.get(aid, 0.0)
            # 2026-08 修复：固定 1 万最低保障对小账户超分配（2万账户防守20%被抬到1万→合计>total）。
            # 改为按账户比例的动态下限（5%，绝对下限 1000），weight=0 保持 0（牛市防守让位）。
            if weight > 0:
                min_cap = max(1000.0, account_total * 0.05)
                target = max(min_cap, account_total * weight)
            else:
                target = 0.0
            current = await self._get_strategy_allocated(sid)

            if abs(target - current) >= 1000:
                await exec_svc.update_allocated_capital(sid, target)
                if self.strategy_manager:
                    self.strategy_manager.update_strategy_capital(sid, target)
                capital_changes.append({
                    "strategy_id": sid, "allocator_id": aid,
                    "old_capital": current, "new_capital": target, "weight": weight,
                })

        # 5. 更新组合状态
        await self.session.execute(text("""
            UPDATE composite_groups
            SET current_regime = :regime, current_allocation = :alloc,
                last_rebalance_at = :now, updated_at = :now
            WHERE id = :id
        """), {"id": group_id, "regime": regime, "alloc": json.dumps(new_allocation),
               "now": datetime.now()})

        # 6. 写组合净值快照
        await self._write_nav_snapshot(group, account_total, regime, new_allocation)

        await self.session.commit()
        logger.info(f"组合 {group_id} rebalance: regime={regime}, alloc={new_allocation}, total={account_total:,.0f}")
        return {"regime": regime, "allocation": new_allocation,
                "account_total": account_total, "capital_changes": capital_changes}

    async def _compute_regime(self) -> int:
        """CSI500 收盘 vs MA250 → 0=熊, 1=震荡, 2=牛"""
        try:
            stmt = text("""
                SELECT close FROM index_daily
                WHERE ts_code = '000905.SH'
                ORDER BY trade_date DESC LIMIT 250
            """)
            rows = (await self.session.execute(stmt)).fetchall()
            closes = [float(r[0]) for r in rows if r[0] is not None]
            if len(closes) < 250:
                return 1
            ma250 = sum(closes) / len(closes)
            close = closes[0]
            if close < ma250 * 0.97:
                return 0
            elif close > ma250 * 1.03:
                return 2
            return 1
        except Exception as e:
            logger.warning(f"regime 判定失败(默认RANGE): {e}")
            return 1

    async def _get_account_total(self, account_id: str) -> float:
        try:
            stmt = text("SELECT total_balance FROM accounts WHERE id = :aid")
            row = (await self.session.execute(stmt, {"aid": account_id})).first()
            return float(row[0]) if row and row[0] else 0.0
        except Exception:
            return 0.0

    async def _get_total_allocated(self, strategy_ids: list) -> float:
        ids = [cfg["strategy_id"] for cfg in strategy_ids]
        if not ids:
            return 0.0
        stmt = text("SELECT COALESCE(SUM(allocated_capital), 0) FROM strategies WHERE id = ANY(:ids)")
        row = (await self.session.execute(stmt, {"ids": ids})).first()
        return float(row[0]) if row and row[0] else 0.0

    async def _get_strategy_allocated(self, sid: str) -> float:
        stmt = text("SELECT allocated_capital FROM strategies WHERE id = :sid")
        row = (await self.session.execute(stmt, {"sid": sid})).first()
        return float(row[0]) if row and row[0] else 0.0

    async def _write_nav_snapshot(self, group, account_total, regime, allocation) -> None:
        """写组合净值快照（composite_account_snapshots）。"""
        try:
            per_strategy = {}
            for cfg in group["strategy_ids"]:
                per_strategy[cfg["strategy_id"]] = await self._get_strategy_allocated(cfg["strategy_id"])
            # 持仓市值 = 组内策略所有持仓 market_value 之和；cash = 总资产 - 市值
            _ids = [cfg["strategy_id"] for cfg in group["strategy_ids"]]
            mv = 0.0
            if _ids:
                _mv = (await self.session.execute(
                    text("SELECT COALESCE(SUM(market_value), 0) FROM positions WHERE strategy_id = ANY(:ids)"),
                    {"ids": _ids},
                )).first()
                if _mv and _mv[0]:
                    mv = float(_mv[0])
            cash = max(0.0, float(account_total) - mv)
            # 真实日收益：对比上一交易日快照（首日无前值则为 0）
            daily_return = 0.0
            _today = date.today()
            prev = (await self.session.execute(
                text("""
                    SELECT total_nav FROM composite_account_snapshots
                    WHERE composite_group_id = :gid AND trade_date < :d
                    ORDER BY trade_date DESC LIMIT 1
                """),
                {"gid": group["id"], "d": _today},
            )).first()
            if prev and prev[0]:
                prev_nav = float(prev[0])
                if prev_nav > 0:
                    daily_return = (float(account_total) - prev_nav) / prev_nav
            stmt = text("""
                INSERT INTO composite_account_snapshots
                (id, composite_group_id, trade_date, total_nav, daily_return,
                 cash, market_value, per_strategy, regime, allocation, created_at)
                VALUES (:id, :gid, :d, :nav, :dr, :cash, :mv, :ps, :regime, :alloc, :now)
                ON CONFLICT (composite_group_id, trade_date) DO UPDATE SET
                    total_nav = EXCLUDED.total_nav,
                    daily_return = EXCLUDED.daily_return,
                    cash = EXCLUDED.cash,
                    market_value = EXCLUDED.market_value,
                    per_strategy = EXCLUDED.per_strategy,
                    regime = EXCLUDED.regime,
                    allocation = EXCLUDED.allocation,
                    created_at = EXCLUDED.created_at
            """)
            await self.session.execute(stmt, {
                "id": str(uuid.uuid4()),
                "gid": group["id"],
                "d": _today,
                "nav": float(account_total),
                "dr": daily_return,
                "cash": cash,
                "mv": mv,
                "ps": json.dumps(per_strategy),
                "regime": regime,
                "alloc": json.dumps(allocation),
                "now": datetime.now(),
            })
        except Exception as e:
            logger.warning(f"组合净值快照写入失败(非致命): {e}")

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _was_triggered_today(self, strategy_id: str, trade_date_str: str) -> bool:
        """检查策略今天是否已触发过"""
        stmt = text("""
            SELECT 1 FROM signals
            WHERE strategy_id = :sid
              AND created_at::date = :d::date
              AND signal_status = 'pending_manual'
            LIMIT 1
        """)
        row = (await self.session.execute(stmt, {"sid": strategy_id, "d": trade_date_str})).first()
        return row is not None

    @staticmethod
    def _safe_json(v):
        """兼容 jsonb 列（返回 dict/list）与 text 列（JSON 字符串）的取值。

        jsonb 列经 asyncpg 反序列化后已是 dict/list，再 json.loads 会抛
        "JSON object must be str, bytes or bytearray"。统一按类型安全解析。
        """
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v

    def _row_to_dict(self, row) -> dict:
        """将 DB row 转为 dict"""
        r = dict(row._mapping)
        for k in ("strategy_ids", "allocator_config", "current_allocation"):
            if k in r and isinstance(r[k], str):
                try:
                    r[k] = json.loads(r[k])
                except (json.JSONDecodeError, TypeError):
                    pass
        result = {
            "id": r.get("id"),
            "name": r.get("name"),
            "account_id": r.get("account_id"),
            "strategy_ids": r.get("strategy_ids") or [],
            "allocator_config": r.get("allocator_config") or {},
            "current_regime": r.get("current_regime", 1),
            "current_allocation": r.get("current_allocation"),
            "status": r.get("status", "active"),
            "last_rebalance_at": str(r.get("last_rebalance_at")) if r.get("last_rebalance_at") else None,
            "created_at": str(r.get("created_at")) if r.get("created_at") else None,
        }
        return result
