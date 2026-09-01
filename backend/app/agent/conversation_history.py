"""
对话历史管理模块

功能：
- 保存问诊对话记录
- 查询历史对话
- 导出对话数据
"""

import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("conversation_history")

# 对话历史存储目录
HISTORY_DIR = Path(__file__).parent.parent.parent / "data" / "conversations"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_conversation(
    conversation_id: str,
    user_id: str,
    user_message: str,
    bot_response: str,
    intent: str,
    steps: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    保存对话记录
    
    Args:
        conversation_id: 会话ID
        user_id: 用户ID
        user_message: 用户消息
        bot_response: 机器人回复
        intent: 意图类型
        steps: 处理步骤
        metadata: 额外元数据
    
    Returns:
        是否保存成功
    """
    try:
        conversation_file = HISTORY_DIR / f"{conversation_id}.json"
        
        # 读取现有对话或创建新对话
        if conversation_file.exists():
            with open(conversation_file, 'r', encoding='utf-8') as f:
                conversation = json.load(f)
        else:
            conversation = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
        
        # 添加新消息
        message = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "bot_response": bot_response,
            "intent": intent,
            "steps": steps,
            "metadata": metadata or {}
        }
        
        conversation["messages"].append(message)
        conversation["updated_at"] = datetime.now().isoformat()
        
        # 保存到文件
        with open(conversation_file, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        
        logger.info(f"对话记录已保存: {conversation_id}")
        return True
        
    except Exception as e:
        logger.error(f"保存对话记录失败: {e}", exc_info=True)
        return False


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    获取对话记录
    
    Args:
        conversation_id: 会话ID
    
    Returns:
        对话记录或None
    """
    try:
        conversation_file = HISTORY_DIR / f"{conversation_id}.json"
        
        if not conversation_file.exists():
            return None
        
        with open(conversation_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        logger.error(f"读取对话记录失败: {e}", exc_info=True)
        return None


def list_conversations(
    user_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    列出对话记录
    
    Args:
        user_id: 用户ID（可选，用于过滤）
        limit: 返回数量限制
        offset: 偏移量
    
    Returns:
        对话记录列表
    """
    try:
        conversations = []
        
        # 遍历所有对话文件
        for file_path in sorted(HISTORY_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if len(conversations) >= limit + offset:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                
                # 过滤用户ID
                if user_id and conversation.get("user_id") != user_id:
                    continue
                
                # 只返回摘要信息
                summary = {
                    "conversation_id": conversation.get("conversation_id"),
                    "user_id": conversation.get("user_id"),
                    "created_at": conversation.get("created_at"),
                    "updated_at": conversation.get("updated_at"),
                    "message_count": len(conversation.get("messages", [])),
                    "last_message": conversation.get("messages", [{}])[-1].get("user_message", "") if conversation.get("messages") else ""
                }
                
                conversations.append(summary)
                
            except Exception as e:
                logger.warning(f"读取对话文件失败 {file_path}: {e}")
                continue
        
        # 应用分页
        return conversations[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"列出对话记录失败: {e}", exc_info=True)
        return []


def delete_conversation(conversation_id: str) -> bool:
    """
    删除对话记录
    
    Args:
        conversation_id: 会话ID
    
    Returns:
        是否删除成功
    """
    try:
        conversation_file = HISTORY_DIR / f"{conversation_id}.json"
        
        if conversation_file.exists():
            conversation_file.unlink()
            logger.info(f"对话记录已删除: {conversation_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"删除对话记录失败: {e}", exc_info=True)
        return False


def export_conversations(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    导出对话记录
    
    Args:
        user_id: 用户ID（可选）
    
    Returns:
        完整对话记录列表
    """
    try:
        conversations = []
        
        for file_path in HISTORY_DIR.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                
                if user_id and conversation.get("user_id") != user_id:
                    continue
                
                conversations.append(conversation)
                
            except Exception as e:
                logger.warning(f"读取对话文件失败 {file_path}: {e}")
                continue
        
        return conversations
        
    except Exception as e:
        logger.error(f"导出对话记录失败: {e}", exc_info=True)
        return []


def get_conversation_stats() -> Dict[str, Any]:
    """
    获取对话统计信息
    
    Returns:
        统计信息
    """
    try:
        total_conversations = 0
        total_messages = 0
        intent_counts = {}
        
        for file_path in HISTORY_DIR.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                
                total_conversations += 1
                messages = conversation.get("messages", [])
                total_messages += len(messages)
                
                # 统计意图
                for msg in messages:
                    intent = msg.get("intent", "unknown")
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1
                    
            except Exception as e:
                logger.warning(f"读取对话文件失败 {file_path}: {e}")
                continue
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "intent_counts": intent_counts
        }
        
    except Exception as e:
        logger.error(f"获取对话统计失败: {e}", exc_info=True)
        return {
            "total_conversations": 0,
            "total_messages": 0,
            "intent_counts": {}
        }
