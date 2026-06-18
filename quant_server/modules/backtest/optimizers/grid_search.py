# -*- coding: utf-8 -*-
"""
网格搜索优化器

负责使用网格搜索方法优化策略参数
"""
import logging
from typing import Dict, List, Any, Callable, Tuple
import itertools

logger = logging.getLogger(__name__)


class GridSearch:
    """
    网格搜索优化器
    
    使用网格搜索方法优化策略参数
    """
    
    def __init__(self):
        """
        初始化网格搜索优化器
        """
        pass
    
    async def optimize(self, objective: Callable, parameters: Dict[str, List[Any]]) -> Tuple[Dict[str, Any], float]:
        """
        执行网格搜索优化
        
        Args:
            objective: 目标函数
            parameters: 参数范围 {param_name: [values]}
            
        Returns:
            (最佳参数, 最佳得分)
        """
        try:
            import asyncio
            
            logger.info(f"开始网格搜索优化，参数空间大小: {self._calculate_space_size(parameters)}")
            
            # 生成参数组合（标量值自动包装为单元素列表）
            param_names = list(parameters.keys())
            param_values = [self._ensure_list(v) for v in parameters.values()]
            param_combinations = list(itertools.product(*param_values))
            
            # 并行执行目标函数评估
            async def evaluate_param(params):
                """评估单个参数组合"""
                param_dict = dict(zip(param_names, params))
                score = await objective(**param_dict)
                return param_dict, score
            
            # 创建任务列表
            tasks = [evaluate_param(params) for params in param_combinations]
            
            # 并行执行所有任务
            results = await asyncio.gather(*tasks)
            
            # 寻找最佳参数
            best_params = None
            best_score = -float('inf')
            
            for eval_param_dict, eval_score in results:
                if eval_score > best_score:
                    best_score = eval_score
                    best_params = eval_param_dict
                    logger.info(f"找到更优参数: {best_params}, 得分: {best_score}")
            
            logger.info(f"网格搜索完成，最佳参数: {best_params}, 最佳得分: {best_score}")
            
            return best_params, best_score
        except Exception as e:
            logger.error(f"网格搜索优化失败: {str(e)}")
            raise
    
    @staticmethod
    def _ensure_list(value: Any) -> List[Any]:
        """将标量值包装为列表，列表值原样返回"""
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

    @staticmethod
    def _calculate_space_size(parameters: Dict[str, Any]) -> int:
        """
        计算参数空间大小

        Args:
            parameters: 参数范围 — 值可以是 list（候选值）或标量（固定值）

        Returns:
            参数空间大小
        """
        size = 1
        for values in parameters.values():
            if isinstance(values, (list, tuple, set)):
                size *= len(values)
            # 标量值 → 只有 1 种可能，乘 1 不改变 size
        return size