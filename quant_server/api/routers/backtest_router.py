# -*- coding: utf-8 -*-
"""
回测模块API路由
基于混合架构设计，负责将HTTP请求路由到回测模块的业务处理层
位置：quant_server/api/routers/backtest_router.py
回测模块路由
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
# 导入架构依赖
from api.dependencies.database import get_db_session
# 导入回测模块的业务层处理函数
from modules.backtest.handlers import (
	create_backtest_task,
	get_backtest_task,
	get_backtest_task_list,
	cancel_backtest_task,
	delete_backtest_task,
	export_backtest_report,
	quick_backtest,
	get_backtest_equity_curve,
	get_backtest_trades,
	get_backtest_positions,
	get_backtest_result,
	optimize_backtest_parameters,
	check_backtest_module_health
)
# 导入回测模块的Pydantic模型
from modules.backtest.schemas import (
	BacktestCreateResponse,
	BacktestDetailResponse,
	BacktestListRequest,
	BacktestListResponse,
	BacktestEquityCurveResponse,
	BacktestTradesResponse,
	BacktestPositionsResponse,
	BacktestResultResponse,
	BacktestOptimizeRequest,
	BacktestOptimizeResponse,
		ScenarioRunRequest,
		ScenarioPromoteRequest,
	BacktestCreateRequest,
	BacktestCompositeCreateRequest,
)
# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	tags=["回测工作台"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 回测任务管理接口 ====================

@router.post("/tasks", response_model=BacktestCreateResponse, status_code=201)
async def create_backtest_api(
		request: BacktestCreateRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestCreateResponse:
	"""
	创建回测任务

	Args:
		request: 回测创建请求
		background_tasks: 后台任务
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestCreateResponse: 创建的回测任务响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 创建回测任务，参数: {request.model_dump()}")

		result = await create_backtest_task(
			session=db_session,
			request=request,
			user_id=current_user.get("id"),
			background_tasks=background_tasks
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建回测任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建回测任务失败: {str(e)}"
		)


@router.post("/composite", response_model=BacktestCreateResponse, status_code=201)
async def create_composite_backtest_api(
		request: BacktestCompositeCreateRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestCreateResponse:
	"""
	创建组合回测任务 — 多策略共享资金池 + CapitalAllocator 动态分配

	Args:
		request: 组合回测创建请求（strategy_configs, 区间, 资金, force_regime等）
		background_tasks: 后台任务
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestCreateResponse: { task_id, status }
	"""
	try:
		from modules.backtest.handlers import create_composite_task

		logger.info(
			f"用户 {current_user.get('username')} 创建组合回测, "
			f"策略数={len(request.strategy_configs)}, "
			f"regime={request.force_regime}"
		)

		result = await create_composite_task(
			session=db_session,
			request=request,
			user_id=current_user.get("id"),
			background_tasks=background_tasks
		)
		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建组合回测失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建组合回测失败: {str(e)}"
		)


@router.get("/tasks", response_model=BacktestListResponse)
async def get_backtest_list_api(
		request: BacktestListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestListResponse:
	"""
	获取回测任务列表

	Args:
		request: 回测列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestListResponse: 回测任务列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求回测任务列表")

		result = await get_backtest_task_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取回测任务列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测任务列表失败: {str(e)}"
		)


@router.get("/tasks/{task_id}", response_model=BacktestDetailResponse)
async def get_backtest_detail_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestDetailResponse:
	"""
	获取回测任务详情

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestDetailResponse: 回测任务详情响应
	"""
	try:
		logger.debug(f"用户 {current_user.get('username')} 请求回测任务详情，任务ID: {task_id}")

		result = await get_backtest_task(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"回测任务不存在: {task_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"回测任务 {task_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取回测任务详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测任务详情失败: {str(e)}"
		)


@router.post("/tasks/{task_id}/cancel", response_model=BacktestCreateResponse)
async def cancel_backtest_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestCreateResponse:
	"""
	取消回测任务

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestDetailResponse: 取消后的任务详情
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 取消回测任务 {task_id}")
		# 通知 BackgroundTaskExecutor 取消（如在线程池中运行）		try:			from shared.utils.background_executor import get_background_executor			executor = get_background_executor()			if executor is not None:				executor.cancel(task_id)		except ImportError:			pass
		result = await cancel_backtest_task(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"回测任务不存在或无法取消: {task_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"取消回测任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"取消回测任务失败: {str(e)}"
		)


@router.delete("/tasks/{task_id}", status_code=200, response_model=None)
async def delete_backtest_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	删除回测任务（级联删除关联数据）

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 删除回测任务 {task_id}")

		await delete_backtest_task(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return success_response(
			message="回测任务删除成功",
			data={"task_id": task_id}
		)

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"回测任务不存在: {task_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"删除回测任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"删除回测任务失败: {str(e)}"
		)


# ==================== 回测结果查询接口 ====================

@router.get("/tasks/{task_id}/equity", response_model=BacktestEquityCurveResponse)
async def get_backtest_equity_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestEquityCurveResponse:
	"""
	获取回测净值曲线

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestEquityCurveResponse: 净值曲线响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求回测净值曲线，任务ID: {task_id}")

		result = await get_backtest_equity_curve(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取回测净值曲线失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测净值曲线失败: {str(e)}"
		)


@router.get("/tasks/{task_id}/trades", response_model=BacktestTradesResponse)
async def get_backtest_trades_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestTradesResponse:
	"""
	获取回测交易记录（分页）

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestTradesResponse: 交易记录响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求回测交易记录，任务ID: {task_id}")

		result = await get_backtest_trades(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取回测交易记录（分页）失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测交易记录（分页）失败: {str(e)}"
		)


@router.get("/tasks/{task_id}/positions", response_model=BacktestPositionsResponse)
async def get_backtest_positions_api(
		task_id: str,
		trade_date: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestPositionsResponse:
	"""
	获取回测持仓快照

	Args:
		task_id: 回测任务ID
		trade_date: 交易日期
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestPositionsResponse: 持仓快照响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求回测持仓快照，任务ID: {task_id}, 日期: {trade_date}")

		result = await get_backtest_positions(
			session=db_session,
			task_id=task_id,
			trade_date=trade_date,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取回测持仓快照失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测持仓快照失败: {str(e)}"
		)


@router.get("/tasks/{task_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result_api(
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestResultResponse:
	"""
	获取回测结果

	Args:
		task_id: 回测任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestResultResponse: 回测结果响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求回测结果，任务ID: {task_id}")

		result = await get_backtest_result(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取回测结果失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取回测结果失败: {str(e)}"
		)


@router.post("/tasks/results/batch", response_model=BacktestResultResponse)
async def get_batch_task_results_api(
    task_ids: List[str] = Body(..., embed=True),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestResultResponse:
    """
    批量获取回测任务结果

    Args:
        task_ids: 回测任务ID列表
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestResultResponse: { success, data: { task_id: result, ... } }
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 批量请求回测结果，任务数: {len(task_ids)}")
        results = {}
        for task_id in task_ids:
            try:
                result = await get_backtest_result(
                    session=db_session,
                    task_id=task_id,
                    user_id=current_user.get("id")
                )
                if result and result.get("success"):
                    results[task_id] = result.get("data", result)
            except Exception:
                pass  # skip failed tasks
        return {
            "success": True,
            "message": f"批量获取完成，成功 {len(results)}/{len(task_ids)}",
            "data": results,
            "timestamp": datetime.now(timezone.utc),
        }
    except Exception as e:
        logger.error(f"批量获取回测结果失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量获取回测结果失败: {str(e)}"
        )


# ==================== 快速回测接口 ====================

@router.post("/quick", status_code=200, response_model=None)
async def quick_backtest_api(
		request: BacktestCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestCreateResponse:
	"""
	快速回测：一步完成策略代码执行+回测+返回结果（同步等待）
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起快速回测")
		result = await quick_backtest(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)
		return result
	except Exception as e:
		logger.error(f"快速回测失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


# ==================== 报告导出接口 ====================

@router.get("/tasks/{task_id}/report/export")
async def export_report_api(
		task_id: str,
		report_format: str = "json",
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	导出回测报告

	Args:
		task_id: 回测任务ID
		report_format: 导出格式 (json / csv)
	"""
	try:
		result = await export_backtest_report(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id"),
			report_format=report_format,
		)
		return success_response(data=result.get("data", result), message="报告导出成功")
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except Exception as e:
		logger.error(f"导出报告失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


# ==================== 参数优化接口 ====================

@router.post("/optimize", response_model=BacktestOptimizeResponse)
async def optimize_parameters_api(
		request: BacktestOptimizeRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BacktestOptimizeResponse:
	"""
	参数优化

	Args:
		request: 参数优化请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		BacktestOptimizeResponse: 参数优化响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求参数优化，参数: {request.model_dump()}")

		result = await optimize_backtest_parameters(
			session=db_session,
			request=request
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"参数优化失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"参数优化失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def backtest_module_health_check(
		current_user: Dict = Depends(get_current_user),
):
	"""
	回测模块健康检查

	Args:
		current_user: 当前登录用户

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.debug(f"用户 {current_user.get('username')} 请求回测模块健康检查")

		health_status = await check_backtest_module_health()

		return success_response(
			data=health_status,
			message="回测模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"回测模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="回测模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)


# =============================================================================
# v3.3: 独立场景回测 + 晋升
# =============================================================================

@router.post("/run-scenario", response_model=BacktestCreateResponse, status_code=201)
async def run_scenario_backtest(
		request: ScenarioRunRequest,
		background_tasks: BackgroundTasks,
		current_user: dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""
	独立场景回测（v3.3）：不依赖策略，直接用代码+参数运行回测。

	Args:
		request: 场景回测请求（name, code, parameters, config）
		current_user: 当前用户
		db: 数据库会话

	Returns:
		{"scenario_id": str, "task_id": str}
	"""
	try:
		from modules.backtest.services.backtest_service import BacktestService

		service = BacktestService(db)
		result = await service.run_scenario(
			user_id=current_user.get("id", ""),
			name=request.name,
			code=request.code,
			parameters=request.parameters,
			config=request.config,
			template_id=getattr(request, "template_id", None),
			source_strategy_id=getattr(request, "source_strategy_id", None),
		)

		# 启动回测 — 提交到独立线程池
		try:
			from shared.utils.background_executor import (
				get_background_executor, TaskPriority,
			)
			from modules.backtest.handlers import _run_backtest_in_thread
			executor = get_background_executor()
			if executor is not None:
				await executor.submit(
					"backtest", result["task_id"],
					coro_factory=lambda: _run_backtest_in_thread(result["task_id"]),
					priority=TaskPriority.BACKGROUND,
				)
			else:
				background_tasks.add_task(
					BacktestService(db).run_backtest,
					task_id=result["task_id"],
					user_id=current_user.get("id", ""),
				)
		except ImportError:
			background_tasks.add_task(
				BacktestService(db).run_backtest,
				task_id=result["task_id"],
				user_id=current_user.get("id", ""),
			)

		return success_response(
			data=result,
			message="场景回测已创建并开始执行"
		)
	except Exception as e:
		logger.error(f"场景回测创建失败: {str(e)}", exc_info=True)
		return error_response(message=str(e), status_code=500)


@router.post("/promote-scenario", status_code=201)
async def promote_scenario(
		request: ScenarioPromoteRequest,
		current_user: dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""
	场景晋升为策略（v3.3）：将验证通过的独立场景保存为正式策略。

	Args:
		request: 晋升请求（scenario_id, strategy_name）
		current_user: 当前用户
		db: 数据库会话

	Returns:
		{"strategy_id": str}
	"""
	try:
		from modules.backtest.services.backtest_service import BacktestService

		service = BacktestService(db)
		result = await service.promote_scenario_to_strategy(
			scenario_id=request.scenario_id,
			user_id=current_user.get("id", ""),
			strategy_name=getattr(request, "strategy_name", None),
		)
		return success_response(
			data=result,
			message="场景已晋升为策略"
		)
	except Exception as e:
		logger.error(f"场景晋升失败: {str(e)}", exc_info=True)
		return error_response(message=str(e), status_code=500)
