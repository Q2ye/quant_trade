"""
数据质量事件定义
用于数据质量检查过程中的事件通知

业务场景：
1. 批量数据质量检查
2. 实时数据质量监控
3. 质量异常报警
4. 质量报告生成
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.modules.data.events.types import DataEventType


class DataQualityCheckStartedEvent(BaseEvent):
    """
    数据质量检查开始事件

    触发时机：
    - 手动触发质量检查
    - 定时任务触发检查
    - 数据同步后自动检查

    事件数据：
    - check_type: 检查类型（完整检查/增量检查）
    - target_tables: 检查的数据表列表
    - check_rules: 应用的检查规则
    """

    def __init__(
        self,
        check_type: str,
        target_tables: List[str],
        check_rules: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            module="events",
            event_type=DataEventType.QUALITY_CHECK_STARTED.value,
            priority=EventPriority.NORMAL,
            source="data_quality_engine",
            **kwargs
        )

        self.data = {
            "check_type": check_type,
            "target_tables": target_tables,
            "check_rules": check_rules or ["basic", "completeness", "consistency"],
            "start_time": datetime.now().isoformat(),
            "total_tables": len(target_tables),
            "checked_tables": 0
        }


def _get_fix_suggestion(issue_type: str) -> str:
    """根据问题类型提供修复建议"""
    suggestions = {
        "missing_value": "检查数据源或使用插值法填充",
        "outlier": "验证数据准确性或使用Winsorize处理",
        "duplicate": "删除重复记录或标记为重复",
        "inconsistent_format": "统一数据格式标准",
        "out_of_range": "检查数据采集过程",
        "null_inconsistency": "明确NULL值处理策略"
    }
    return suggestions.get(issue_type, "需要人工检查")


class DataQualityIssueFoundEvent(BaseEvent):
    """
    发现数据质量问题事件

    触发时机：
    - 数据质量检查过程中发现问题
    - 实时数据验证失败

    事件数据：
    - issue_type: 问题类型（缺失值/异常值/重复值等）
    - severity: 严重程度（低/中/高/严重）
    - affected_data: 受影响的数据信息
    - issue_details: 问题详细信息
    """

    def __init__(
        self,
        issue_type: str,
        table_name: str,
        column_name: str,
        severity: str = "medium",
        affected_count: int = 1,
        issue_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            module="events",
            event_type=DataEventType.QUALITY_ISSUE_FOUND.value,
            priority=EventPriority.HIGH if severity in ["high", "critical"] else EventPriority.NORMAL,
            source="data_quality_engine",
            **kwargs
        )

        self.data = {
            "issue_type": issue_type,
            "table_name": table_name,
            "column_name": column_name,
            "severity": severity,
            "affected_count": affected_count,
            "issue_details": issue_details or {},
            "detection_time": datetime.now().isoformat(),
            "status": "detected",  # detected, acknowledged, fixed
            "fix_suggestion": _get_fix_suggestion(issue_type)
        }


def _calculate_quality_score(pass_rate: float, issue_summary: Dict[str, int]) -> float:
    """
    计算数据质量评分
    基于通过率和问题严重程度
    """
    base_score = pass_rate

    # 根据问题类型扣分
    penalty = 0
    for issue_type, count in issue_summary.items():
        if issue_type == "critical":
            penalty += count * 10
        elif issue_type == "high":
            penalty += count * 5
        elif issue_type == "medium":
            penalty += count * 2
        else:
            penalty += count * 0.5

    # 最终得分（0-100）
    final_score = max(0, base_score - penalty)
    return round(final_score, 1)


class DataQualityCheckCompletedEvent(BaseEvent):
    """
    数据质量检查完成事件

    触发时机：
    - 质量检查任务完成
    - 所有检查规则执行完毕

    事件数据：
    - summary: 检查结果汇总
    - statistics: 检查统计信息
    - report_url: 质量报告地址
    """

    def __init__(
        self,
        check_id: str,
        total_checks: int,
        passed_checks: int,
        failed_checks: int,
        issue_summary: Dict[str, int],
        duration_seconds: float,
        report_path: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            module="events",
            event_type=DataEventType.QUALITY_CHECK_COMPLETED.value,
            priority=EventPriority.NORMAL,
            source="data_quality_engine",
            **kwargs
        )

        # 计算通过率
        pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 100

        self.data = {
            "check_id": check_id,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "pass_rate": round(pass_rate, 2),
            "issue_summary": issue_summary,
            "duration_seconds": round(duration_seconds, 2),
            "report_path": report_path,
            "completion_time": datetime.now().isoformat(),
            "quality_score": _calculate_quality_score(pass_rate, issue_summary)
        }

