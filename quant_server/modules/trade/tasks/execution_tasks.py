# execution_tasks.py   # 执行任务

import asyncio
from typing import Dict, Any, List
from datetime import datetime
from core.engines.system import EventEngine
from modules.trade.engines.execution_engine import ExecutionEngine
from modules.trade.events.execution_events import OrderUpdateEvent


class ExecutionTasks:
    """执行任务类"""
    
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        event_engine: EventEngine
    ):
        """
        初始化执行任务
        
        Args:
            execution_engine: 执行引擎
            event_engine: 事件引擎
        """
        self.execution_engine = execution_engine
        self.event_engine = event_engine
        self.tasks = []
        self.pending_orders = set()  # 待处理的订单
    
    async def start(self):
        """启动执行任务"""
        # 启动订单状态检查任务
        self.tasks.append(asyncio.create_task(self._order_status_check()))
        # 启动订单超时检查任务
        self.tasks.append(asyncio.create_task(self._order_timeout_check()))
    
    async def stop(self):
        """停止执行任务"""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
    
    async def _order_status_check(self):
        """订单状态检查"""
        while True:
            try:
                # 每10秒检查一次订单状态
                await asyncio.sleep(10)
                await self.check_order_statuses()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"订单状态检查出错: {str(e)}")
    
    async def _order_timeout_check(self):
        """订单超时检查"""
        while True:
            try:
                # 每30秒检查一次订单超时
                await asyncio.sleep(30)
                await self.check_order_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"订单超时检查出错: {str(e)}")
    
    async def check_order_statuses(self):
        """检查订单状态"""
        try:
            # 获取所有订单
            orders = self.execution_engine.get_orders()
            
            # 检查每个订单的状态
            for order in orders:
                order_id = order.get("order_id")
                if order_id and order.get("status") in ["pending", "submitted"]:
                    # 检查订单状态
                    status = await self.execution_engine.get_order_status(order_id)
                    
                    # 如果状态发生变化，发布订单更新事件
                    if status and status.get("status") != order.get("status"):
                        if self.event_engine:
                            event = OrderUpdateEvent(
                                order_id=order_id,
                                order_status=status.get("status"),
                                order_data=status
                            )
                            await self.event_engine.put(event)
        except Exception as e:
            print(f"检查订单状态出错: {str(e)}")
    
    async def check_order_timeouts(self):
        """检查订单超时"""
        try:
            # 获取所有订单
            orders = self.execution_engine.get_orders()
            current_time = datetime.now()
            
            # 检查每个订单是否超时
            for order in orders:
                order_id = order.get("order_id")
                if order_id and order.get("status") in ["pending", "submitted"]:
                    # 检查订单是否超时（超过30分钟）
                    created_at = order.get("created_at")
                    if created_at:
                        try:
                            created_time = datetime.fromisoformat(created_at)
                            if (current_time - created_time).total_seconds() > 1800:  # 30分钟
                                # 取消超时订单
                                await self.execution_engine.cancel_order(order_id)
                                # 发布订单更新事件
                                if self.event_engine:
                                    event = OrderUpdateEvent(
                                        order_id=order_id,
                                        order_status="cancelled",
                                        order_data={**order, "status": "cancelled", "reason": "timeout"}
                                    )
                                    await self.event_engine.put(event)
                        except Exception as e:
                            print(f"检查订单超时出错: {str(e)}")
        except Exception as e:
            print(f"检查订单超时出错: {str(e)}")
    
    async def process_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理订单"""
        try:
            # 执行订单
            order = await self.execution_engine.execute_order(order_data)
            
            # 如果订单成功提交，添加到待处理订单列表
            order_id = order.get("order_id")
            if order_id and order.get("status") in ["pending", "submitted"]:
                self.pending_orders.add(order_id)
            
            return {
                "success": order.get("status") in ["pending", "submitted", "filled"],
                "order": order,
                "message": "订单处理完成"
            }
        except Exception as e:
            print(f"处理订单出错: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def batch_process_orders(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理订单"""
        results = []
        for order_data in orders:
            result = await self.process_order(order_data)
            results.append(result)
        return results
    
    async def get_order_statistics(self) -> Dict[str, Any]:
        """获取订单统计信息"""
        try:
            # 获取所有订单
            orders = self.execution_engine.get_orders()
            
            # 统计订单状态
            status_count = {}
            for order in orders:
                status = order.get("status", "unknown")
                status_count[status] = status_count.get(status, 0) + 1
            
            # 生成统计报告
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_orders": len(orders),
                "status_count": status_count,
                "pending_orders": len([o for o in orders if o.get("status") in ["pending", "submitted"]])
            }
            
            return report
        except Exception as e:
            print(f"获取订单统计信息出错: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }