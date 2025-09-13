# api/risk.py 风控API
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from quant_server.api.dependencies import get_db
from quant_server.api.login import get_current_user
from quant_server.db.models.business_models import RiskRule, RiskEvent

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/rules")
async def get_risk_rules(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取风控规则列表"""
    rules = db.query(RiskRule).filter(RiskRule.user_id == current_user.id).all()
    return {"rules": rules}


@router.post("/rules")
async def create_risk_rule(
        rule_data: dict,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """创建风控规则"""
    new_rule = RiskRule(
        user_id=current_user.id,
        **rule_data
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return {"rule": new_rule}


@router.put("/rules/{rule_id}")
async def update_risk_rule(
        rule_id: int,
        rule_data: dict,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """更新风控规则"""
    rule = db.query(RiskRule).filter(
        RiskRule.id == rule_id,
        RiskRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    for key, value in rule_data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return {"rule": rule}


@router.get("/events")
async def get_risk_events(
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取风控事件记录"""
    events = db.query(RiskEvent).filter(
        RiskEvent.user_id == current_user.id
    ).order_by(RiskEvent.created_at.desc()).limit(limit).all()

    return {"events": events}