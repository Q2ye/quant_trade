# -*- coding: utf-8 -*-
"""
策略模板服务
负责策略模板的管理和使用
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.strategy.management import (
    StrategyTemplateRepository,
    StrategyRepository,
)
from modules.strategy.constants import StrategyType

logger = logging.getLogger(__name__)


class TemplateService:
    """
    策略模板服务

    负责：
    - 策略模板的创建和管理
    - 模板分类和检索
    - 基于模板创建策略
    - 模板参数配置
    """

    def __init__(self, session: AsyncSession):
        """
        初始化服务

        Args:
            session: 数据库会话
        """
        self.session = session
        self.template_repo = StrategyTemplateRepository(session)
        self.strategy_repo = StrategyRepository(session)

    async def get_template_list(
        self,
        strategy_type: Optional[StrategyType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取模板列表

        Args:
            strategy_type: 策略类型筛选
            page: 页码
            page_size: 每页数量

        Returns:
            模板列表
        """
        try:
            template_type = strategy_type.value if strategy_type else None

            result = await self.template_repo.get_paginated(
                page=page,
                page_size=page_size,
                template_type=template_type
            )

            templates = result["items"]
            total = result["total"]

            return {
                "success": True,
                "data": [self._to_dict(t) for t in templates],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                }
            }
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
            }

    async def get_template_detail(
        self,
        template_id: str,
    ) -> Dict[str, Any]:
        """
        获取模板详情

        Args:
            template_id: 模板ID

        Returns:
            模板详情
        """
        try:
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {
                    "success": False,
                    "error": f"模板 {template_id} 不存在"
                }

            return {
                "success": True,
                "data": {
                    "id": template.id,
                    "name": template.template_name,
                    "template_name": template.template_name,
                    "description": template.description,
                    "strategy_type": template.template_type,
                    "template_type": template.template_type,
                    "code_template": template.code_template,
                    "default_parameters": self._parse_parameters(template.default_parameters),
                    "category": template.category,
                    "is_public": getattr(template, "is_public", True),
                    "is_builtin": getattr(template, "is_builtin", False),
                    "tags": [],
                    "created_at": template.created_at.isoformat() if template.created_at else None,
                }
            }
        except Exception as e:
            logger.error(f"获取模板详情失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def create_from_template(
        self,
        template_id: str,
        name: str,
        user_id: str,
        custom_parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        基于模板创建策略

        Args:
            template_id: 模板ID
            name: 策略名称
            user_id: 用户ID
            custom_parameters: 自定义参数

        Returns:
            创建结果
        """
        try:
            # 获取模板
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {
                    "success": False,
                    "error": f"模板 {template_id} 不存在"
                }

            # 合并参数
            parameters = self._parse_parameters(template.default_parameters)
            if custom_parameters:
                parameters.update(custom_parameters)

            # 创建策略
            strategy_data = {
                "name": name,
                "description": template.description,
                "strategy_type": template.template_type,
                "code": template.code_template,
                "status": "draft",
                "user_id": user_id,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            strategy = await self.strategy_repo.create(strategy_data)

            logger.info(f"基于模板创建策略: {name}, 模板: {template_id}")

            return {
                "success": True,
                "data": {
                    "id": strategy.id,
                    "name": strategy.name,
                    "template_id": template_id,
                }
            }
        except Exception as e:
            logger.error(f"基于模板创建策略失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def create_template(
        self,
        name: str,
        strategy_type: StrategyType,
        code_template: str,
        description: str = "",
        default_parameters: Optional[Dict[str, Any]] = None,
        category: str = "custom",
    ) -> Dict[str, Any]:
        """
        创建模板

        Args:
            name: 模板名称
            strategy_type: 策略类型
            code_template: 代码模板
            description: 描述
            default_parameters: 默认参数
            category: 分类

        Returns:
            创建结果
        """
        try:
            template_data = {
                "template_name": name,
                "description": description,
                "template_type": strategy_type.value,
                "code_template": code_template,
                "default_parameters": default_parameters or {},
                "category": category,
                "created_at": datetime.now(),
            }

            template = await self.template_repo.create(template_data)

            logger.info(f"创建策略模板: {name}")

            return {
                "success": True,
                "data": {
                    "id": template.id,
                    "name": template.template_name,
                }
            }
        except Exception as e:
            logger.error(f"创建模板失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        code_template: Optional[str] = None,
        default_parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        更新模板

        Args:
            template_id: 模板ID
            name: 模板名称
            description: 描述
            code_template: 代码模板
            default_parameters: 默认参数

        Returns:
            更新结果
        """
        try:
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {
                    "success": False,
                    "error": f"模板 {template_id} 不存在"
                }

            update_data = {}
            if name:
                update_data["template_name"] = name
            if description:
                update_data["description"] = description
            if code_template:
                update_data["code_template"] = code_template
            if default_parameters:
                update_data["default_parameters"] = default_parameters

            await self.template_repo.update(template_id, update_data)

            logger.info(f"更新策略模板: {template_id}")

            return {
                "success": True,
                "data": {"id": template_id}
            }
        except Exception as e:
            logger.error(f"更新模板失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def delete_template(
        self,
        template_id: str,
    ) -> Dict[str, Any]:
        """
        删除模板

        Args:
            template_id: 模板ID

        Returns:
            删除结果
        """
        try:
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {
                    "success": False,
                    "error": f"模板 {template_id} 不存在"
                }

            await self.template_repo.delete(template_id)

            logger.info(f"删除策略模板: {template_id}")

            return {
                "success": True,
                "data": {"id": template_id}
            }
        except Exception as e:
            logger.error(f"删除模板失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _parse_parameters(parameters: Any) -> Dict[str, Any]:
        """解析参数"""
        try:
            if isinstance(parameters, dict):
                return parameters
            elif isinstance(parameters, str):
                import ast
                return ast.literal_eval(parameters) if parameters else {}
            return {}
        except (ValueError, SyntaxError):
            return {}

    @staticmethod
    def _to_dict(template) -> Dict[str, Any]:
        """转换为字典 — v3.0: 增加 is_builtin/template_name/default_parameters"""
        return {
            "id": template.id,
            "name": template.template_name,
            "template_name": template.template_name,
            "description": template.description,
            "strategy_type": template.template_type,
            "template_type": template.template_type,
            "category": template.category,
            "is_public": getattr(template, "is_public", True),
            "is_builtin": getattr(template, "is_builtin", False),
            "default_parameters": getattr(template, "default_parameters", {}),
            "code_template": getattr(template, "code_template", ""),
            "tags": [],
            "created_at": template.created_at.isoformat() if template.created_at else None,
        }
    # ==================== v3.0: 模板种子 + 实例创建 + Fork ====================

    async def seed_builtin_templates(self) -> Dict[str, Any]:
        """
        从 StrategyRegistry 同步内置策略到 strategy_templates 表。

        幂等：按 template_name + is_builtin 去重，已存在则更新代码/参数。
        在 StrategyManager._on_initialize() 中调用。
        """
        import importlib
        import inspect

        from modules.strategy.engines.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()
        if registry.is_empty():
            registry.auto_discover()

        seeded = 0
        skipped = 0

        for entry in registry.list_all():
            strategy_type = entry.get("strategy_type", "")
            class_name = entry.get("class_name", "")
            module_path = entry.get("module", "")
            display_name = entry.get("display_name", class_name)

            # 提取源代码
            source_code = ""
            try:
                mod = importlib.import_module(module_path)
                for cls_obj in mod.__dict__.values():
                    if inspect.isclass(cls_obj) and cls_obj.__name__ == class_name:
                        source_code = inspect.getsource(cls_obj)
                        break
            except Exception:
                pass

            # 提取默认参数
            default_params = {}
            try:
                mod = importlib.import_module(module_path)
                for cls_obj in mod.__dict__.values():
                    if inspect.isclass(cls_obj) and cls_obj.__name__ == class_name:
                        try:
                            tmp = cls_obj()
                        except TypeError:
                            tmp = cls_obj(name=class_name)
                        if hasattr(tmp, "get_parameters"):
                            default_params = tmp.get_parameters()
                        elif hasattr(tmp, "parameters") and tmp.parameters:
                            default_params = dict(tmp.parameters)
                        if not default_params and hasattr(cls_obj, "DEFAULT_PARAMS"):
                            default_params = dict(getattr(cls_obj, "DEFAULT_PARAMS", {}))
                        break
            except Exception:
                pass

            # 幂等检查
            existing = await self.template_repo.get_many(
                template_name=display_name,
                is_builtin=True,
                limit=1,
            )
            if existing:
                await self.template_repo.update(existing[0].id, {
                    "code_template": source_code or existing[0].code_template,
                    "default_parameters": default_params or existing[0].default_parameters,
                })
                skipped += 1
                continue

            await self.template_repo.create({
                "template_name": display_name,
                "template_type": strategy_type,
                "description": f"{display_name} — 基于{strategy_type}类型的量化交易策略",
                "code_template": source_code,
                "default_parameters": default_params,
                "category": "builtin",
                "is_public": True,
                "is_builtin": True,
            })
            seeded += 1

        await self.session.commit()
        return {"success": True, "data": {"seeded": seeded, "skipped": skipped}}

    async def create_instance_from_template(
        self,
        template_id: str,
        user_id: str,
        name: str = "",
        account_id: str = None,
        capital: float = 1000000.0,
        run_mode: str = "backtest",
    ) -> Dict[str, Any]:
        """
        从模板创建策略实例（strategies 行）。
        设置 template_id FK，代码从模板读取。
        """
        import re
        try:
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {"success": False, "error": f"模板 {template_id} 不存在"}

            # 从代码中提取类名
            match = re.search(r'class\s+(\w+)\s*[(:]', template.code_template or "")
            class_name = match.group(1) if match else "Strategy"

            strategy_data = {
                "name": name or template.template_name,
                "description": template.description or "",
                "strategy_type": template.template_type,
                "code": template.code_template,
                "class_name": class_name,
                "module_path": f"strategies.user_{user_id}.{class_name.lower()}",
                "template_id": template_id,
                "status": "draft",
                "run_mode": run_mode,
                "account_id": account_id,
                "allocated_capital": capital,
                "user_id": user_id,
            }

            strategy = await self.strategy_repo.create(strategy_data)
            await self.session.commit()

            return {
                "success": True,
                "data": {"id": strategy.id, "name": strategy.name, "template_id": template_id},
            }
        except Exception as e:
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def fork_template(
        self,
        template_id: str,
        new_name: str = "",
    ) -> Dict[str, Any]:
        """Fork 模板，新模板设置 source_template_id 追踪来源"""
        try:
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                return {"success": False, "error": f"模板 {template_id} 不存在"}

            fork_data = {
                "template_name": new_name or f"{template.template_name}_副本",
                "template_type": template.template_type,
                "description": f"Forked from {template.template_name}",
                "code_template": template.code_template,
                "default_parameters": dict(template.default_parameters) if template.default_parameters else {},
                "category": template.category or "custom",
                "is_public": False,
                "is_builtin": False,
                "source_template_id": template_id,
                "created_by": template.created_by,
            }

            new_template = await self.template_repo.create(fork_data)
            await self.session.commit()

            return {"success": True, "data": {"id": new_template.id, "name": new_template.template_name}}
        except Exception as e:
            await self.session.rollback()
            return {"success": False, "error": str(e)}
