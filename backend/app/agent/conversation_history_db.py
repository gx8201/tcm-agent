"""
对话历史管理模块（数据库版本）

功能：
- 保存问诊对话记录（用户隔离）
- 查询历史对话
- 导出对话数据
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User

logger = logging.getLogger("conversation_history")


def save_conversation(
    conversation_id: str,
    user_id: int,
    user_message: str,
    bot_response: str,
    intent: str,
    steps: List[str],
    metadata: Optional[Dict[str, Any]] = None,
    db: Session = None
) -> bool:
    """
    保存对话记录（数据库版本）
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID（整数）
        user_message: 用户消息
        bot_response: 机器人回复
        intent: 意图类型
        steps: 处理步骤
        metadata: 额外元数据
        db: 数据库会话
    
    Returns:
        是否保存成功
    """
    if db is None:
        logger.error("数据库会话未提供")
        return False
    
    try:
        # 查找或创建对话记录
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            conversation = Conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                title=user_message[:50] + "..." if len(user_message) > 50 else user_message
            )
            db.add(conversation)
            db.flush()  # 获取 ID
        
        # 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
            intent=intent,
            steps=steps,
            metadata=metadata
        )
        db.add(user_msg)
        
        # 保存机器人回复
        bot_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=bot_response,
            intent=intent,
            steps=steps,
            metadata=metadata
        )
        db.add(bot_msg)
        
        # 更新对话时间
        conversation.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"对话记录已保存: {conversation_id}")
        return True
        
    except Exception as e:
        logger.error(f"保存对话记录失败: {e}", exc_info=True)
        db.rollback()
        return False


def get_conversation(conversation_id: str, user_id: int = None, db: Session = None) -> Optional[Dict[str, Any]]:
    """
    获取对话记录
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID（可选，用于权限检查）
        db: 数据库会话
    
    Returns:
        对话记录或None
    """
    if db is None:
        return None
    
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        # 权限检查
        if user_id and conversation.user_id != user_id:
            return None
        
        # 获取消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).all()
        
        return {
            "conversation_id": conversation.conversation_id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "intent": msg.intent,
                    "steps": msg.steps,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
        
    except Exception as e:
        logger.error(f"读取对话记录失败: {e}", exc_info=True)
        return None


def list_conversations(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = None
) -> List[Dict[str, Any]]:
    """
    列出用户的对话记录
    
    Args:
        user_id: 用户ID
        limit: 返回数量限制
        offset: 偏移量
        db: 数据库会话
    
    Returns:
        对话记录列表
    """
    if db is None:
        return []
    
    try:
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(
            Conversation.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        result = []
        for conv in conversations:
            # 获取消息数量
            message_count = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).count()
            
            # 获取最后一条消息
            last_message = db.query(Message).filter(
                Message.conversation_id == conv.id,
                Message.role == "user"
            ).order_by(Message.created_at.desc()).first()
            
            result.append({
                "conversation_id": conv.conversation_id,
                "user_id": conv.user_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "message_count": message_count,
                "last_message": last_message.content if last_message else ""
            })
        
        return result
        
    except Exception as e:
        logger.error(f"列出对话记录失败: {e}", exc_info=True)
        return []


def delete_conversation(conversation_id: str, user_id: int = None, db: Session = None) -> bool:
    """
    删除对话记录
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID（可选，用于权限检查）
        db: 数据库会话
    
    Returns:
        是否删除成功
    """
    if db is None:
        return False
    
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        
        if not conversation:
            return False
        
        # 权限检查
        if user_id and conversation.user_id != user_id:
            return False
        
        db.delete(conversation)
        db.commit()
        logger.info(f"对话记录已删除: {conversation_id}")
        return True
        
    except Exception as e:
        logger.error(f"删除对话记录失败: {e}", exc_info=True)
        db.rollback()
        return False


def get_conversation_stats(user_id: int = None, db: Session = None) -> Dict[str, Any]:
    """
    获取对话统计信息
    
    Args:
        user_id: 用户ID（可选，不提供则统计所有用户）
        db: 数据库会话
    
    Returns:
        统计信息
    """
    if db is None:
        return {"total_conversations": 0, "total_messages": 0, "intent_counts": {}}
    
    try:
        # 统计对话数
        query = db.query(Conversation)
        if user_id:
            query = query.filter(Conversation.user_id == user_id)
        total_conversations = query.count()
        
        # 统计消息数
        message_query = db.query(Message)
        if user_id:
            message_query = message_query.join(Conversation).filter(
                Conversation.user_id == user_id
            )
        total_messages = message_query.count()
        
        # 统计意图分布
        intent_counts = {}
        intents = db.query(Message.intent, func.count(Message.id)).group_by(Message.intent).all()
        for intent, count in intents:
            if intent:
                intent_counts[intent] = count
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "intent_counts": intent_counts
        }
        
    except Exception as e:
        logger.error(f"获取对话统计失败: {e}", exc_info=True)
        return {"total_conversations": 0, "total_messages": 0, "intent_counts": {}}
