"""
数据收集模块（合规版）

功能：
- 收集脱敏的问诊数据用于模型优化
- 用户反馈收集（有效/无效）
- 数据统计和分析
- 符合《个人信息保护法》要求
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from app.database import Base

logger = logging.getLogger("data_collection")


class ConsultationFeedback(Base):
    """问诊反馈表"""
    __tablename__ = "consultation_feedback"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(50), index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    
    # 问诊数据（脱敏）
    symptoms = Column(JSON, nullable=True)  # 症状列表
    intent = Column(String(50), nullable=True)  # 意图类型
    diagnosis_result = Column(String(200), nullable=True)  # 辨证结果
    
    # 用户反馈
    is_helpful = Column(Boolean, nullable=True)  # 是否有帮助
    feedback_text = Column(String(500), nullable=True)  # 反馈文本
    
    # 元数据
    timestamp = Column(DateTime, default=datetime.utcnow)
    region = Column(String(50), nullable=True)  # 地区（可选）
    
    def __repr__(self):
        return f"<ConsultationFeedback(id={self.id}, conversation_id='{self.conversation_id}')>"


def collect_consultation_data(
    conversation_id: str,
    user_id: int,
    symptoms: List[str],
    intent: str,
    diagnosis_result: str,
    db: Session
) -> bool:
    """
    收集脱敏的问诊数据
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID
        symptoms: 症状列表
        intent: 意图类型
        diagnosis_result: 辨证结果
        db: 数据库会话
    
    Returns:
        是否成功
    """
    try:
        feedback = ConsultationFeedback(
            conversation_id=conversation_id,
            user_id=user_id,
            symptoms=symptoms,
            intent=intent,
            diagnosis_result=diagnosis_result
        )
        db.add(feedback)
        db.commit()
        logger.info(f"问诊数据已收集: {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"收集问诊数据失败: {e}")
        db.rollback()
        return False


def submit_feedback(
    conversation_id: str,
    user_id: int,
    is_helpful: bool,
    feedback_text: Optional[str] = None,
    db: Session = None
) -> bool:
    """
    提交用户反馈
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID
        is_helpful: 是否有帮助
        feedback_text: 反馈文本
        db: 数据库会话
    
    Returns:
        是否成功
    """
    if db is None:
        return False
    
    try:
        # 查找对应的问诊记录
        feedback = db.query(ConsultationFeedback).filter(
            ConsultationFeedback.conversation_id == conversation_id,
            ConsultationFeedback.user_id == user_id
        ).first()
        
        if feedback:
            feedback.is_helpful = is_helpful
            feedback.feedback_text = feedback_text
        else:
            # 如果没有找到记录，创建新的
            feedback = ConsultationFeedback(
                conversation_id=conversation_id,
                user_id=user_id,
                is_helpful=is_helpful,
                feedback_text=feedback_text
            )
            db.add(feedback)
        
        db.commit()
        logger.info(f"用户反馈已提交: {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"提交反馈失败: {e}")
        db.rollback()
        return False


def get_feedback_stats(db: Session) -> Dict[str, Any]:
    """
    获取反馈统计
    
    Args:
        db: 数据库会话
    
    Returns:
        统计数据
    """
    try:
        total = db.query(ConsultationFeedback).count()
        helpful = db.query(ConsultationFeedback).filter(
            ConsultationFeedback.is_helpful == True
        ).count()
        not_helpful = db.query(ConsultationFeedback).filter(
            ConsultationFeedback.is_helpful == False
        ).count()
        
        # 计算有效率
        effectiveness_rate = (helpful / total * 100) if total > 0 else 0
        
        return {
            "total_consultations": total,
            "helpful_count": helpful,
            "not_helpful_count": not_helpful,
            "effectiveness_rate": round(effectiveness_rate, 2),
            "pending_feedback": total - helpful - not_helpful
        }
    except Exception as e:
        logger.error(f"获取反馈统计失败: {e}")
        return {
            "total_consultations": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "effectiveness_rate": 0,
            "pending_feedback": 0
        }


def get_symptom_stats(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """
    获取症状统计（用于分析高频症状）
    
    Args:
        db: 数据库会话
        limit: 返回数量限制
    
    Returns:
        症状统计列表
    """
    try:
        # 获取所有症状数据
        feedbacks = db.query(ConsultationFeedback.symptoms).filter(
            ConsultationFeedback.symptoms.isnot(None)
        ).all()
        
        # 统计症状频率
        symptom_count = {}
        for (symptoms,) in feedbacks:
            if symptoms and isinstance(symptoms, list):
                for symptom in symptoms:
                    symptom_count[symptom] = symptom_count.get(symptom, 0) + 1
        
        # 排序并返回
        sorted_symptoms = sorted(symptom_count.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"symptom": symptom, "count": count}
            for symptom, count in sorted_symptoms[:limit]
        ]
    except Exception as e:
        logger.error(f"获取症状统计失败: {e}")
        return []
