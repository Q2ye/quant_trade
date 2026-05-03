# sim_adapter.py        # 模拟交易适配器

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from modules.trade.adapters.broker_adapter import BrokerAdapter


class SimBrokerAdapter(BrokerAdapter):
    """模拟交易适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connected = False
        self.initial_capital = config.get("initial_capital", 1000000)
        self.capital = self.initial_capital
        self.positions = {}
        self.orders = {}
        self.trades = []
    
    async def connect(self) -> bool:
        """连接模拟券商"""
        self.connected = True
        print("模拟券商连接成功")
        return True
    
    async def disconnect(self) -> bool:
        """断开模拟券商"""
        self.connected = False
        print("模拟券商断开连接")
        return True
    
    async def send_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """发送模拟订单"""
        order_id = str(uuid.uuid4())
        order = {
            "order_id": order_id,
            "ts_code": order_data.get("ts_code"),
            "direction": order_data.get("direction"),
            "price": order_data.get("price"),
            "quantity": order_data.get("quantity"),
            "order_type": order_data.get("order_type", "limit"),
            "status": "filled",  # 模拟订单立即成交
            "created_at": datetime.now().isoformat(),
            "filled_at": datetime.now().isoformat(),
            "filled_price": order_data.get("price"),
            "filled_quantity": order_data.get("quantity")
        }
        
        # 模拟成交处理
        await self._process_trade(order)
        
        self.orders[order_id] = order
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """取消模拟订单"""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "cancelled"
            return True
        return False
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """获取订单状态"""
        return self.orders.get(order_id, {})
    
    async def get_position(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓"""
        positions = []
        for ts_code, pos_data in self.positions.items():
            if symbol and ts_code != symbol:
                continue
            positions.append({
                "ts_code": ts_code,
                "quantity": pos_data["quantity"],
                "cost_price": pos_data["cost_price"],
                "current_price": pos_data["current_price"],
                "pnl": pos_data["pnl"]
            })
        return positions
    
    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息"""
        total_asset = self.capital
        for pos_data in self.positions.values():
            total_asset += pos_data["quantity"] * pos_data["current_price"]
        
        return {
            "capital": self.capital,
            "total_asset": total_asset,
            "available": self.capital
        }
    
    def is_connected(self) -> bool:
        """检查是否连接"""
        return self.connected
    
    async def _process_trade(self, order: Dict[str, Any]):
        """处理模拟成交"""
        ts_code = order["ts_code"]
        direction = order["direction"]
        price = order["filled_price"]
        quantity = order["filled_quantity"]
        
        # 更新资金
        if direction == "buy":
            cost = price * quantity
            self.capital -= cost
        else:
            revenue = price * quantity
            self.capital += revenue
        
        # 更新持仓
        if ts_code not in self.positions:
            self.positions[ts_code] = {
                "quantity": 0,
                "cost_price": 0,
                "current_price": price,
                "pnl": 0
            }
        
        pos_data = self.positions[ts_code]
        if direction == "buy":
            total_cost = pos_data["cost_price"] * pos_data["quantity"] + price * quantity
            total_quantity = pos_data["quantity"] + quantity
            pos_data["cost_price"] = total_cost / total_quantity if total_quantity > 0 else 0
            pos_data["quantity"] = total_quantity
        else:
            pos_data["quantity"] -= quantity
            if pos_data["quantity"] <= 0:
                del self.positions[ts_code]
        
        # 更新当前价格和盈亏
        pos_data["current_price"] = price
        if ts_code in self.positions:
            pos_data["pnl"] = (price - pos_data["cost_price"]) * pos_data["quantity"]
        
        # 记录交易
        trade = {
            "trade_id": str(uuid.uuid4()),
            "order_id": order["order_id"],
            "ts_code": ts_code,
            "direction": direction,
            "price": price,
            "quantity": quantity,
            "trade_time": datetime.now().isoformat()
        }
        self.trades.append(trade)