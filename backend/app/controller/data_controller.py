"""
数据收集 API

提供问诊数据收集和用户反馈接口
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.data_collection import (
    collect_consultation_data,
    submit_feedback,
    get_feedback_stats,
    get_symptom_stats
)

router = APIRouter(prefix="/api/v1/data", tags=["数据收集"])


class FeedbackRequest(BaseModel):
    """反馈请求"""
    conversation_id: str
    is_helpful: bool
    feedback_text: Optional[str] = None


class CollectDataRequest(BaseModel):
    """数据收集请求"""
    conversation_id: str
    symptoms: List[str]
    intent: str
    diagnosis_result: str


@router.post("/collect")
async def collect_data(
    request: CollectDataRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收集脱敏的问诊数据"""
    success = collect_consultation_data(
        conversation_id=request.conversation_id,
        user_id=current_user.id,
        symptoms=request.symptoms,
        intent=request.intent,
        diagnosis_result=request.diagnosis_result,
        db=db
    )
    
    if success:
        return {"message": "数据收集成功"}
    else:
        return {"error": "数据收集失败"}


@router.post("/feedback")
async def submit_user_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交用户反馈"""
    success = submit_feedback(
        conversation_id=request.conversation_id,
        user_id=current_user.id,
        is_helpful=request.is_helpful,
        feedback_text=request.feedback_text,
        db=db
    )
    
    if success:
        return {"message": "反馈提交成功"}
    else:
        return {"error": "反馈提交失败"}


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """获取反馈统计（公开接口）"""
    stats = get_feedback_stats(db)
    return stats


@router.get("/symptoms")
async def get_symptoms(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取高频症状统计（公开接口）"""
    symptoms = get_symptom_stats(db, limit)
    return {"symptoms": symptoms}
