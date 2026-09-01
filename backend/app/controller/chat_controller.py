"""
聊天控制器 - SSE 流式输出

精简版：直接调用诊断子图，去除复杂的中间件和记忆系统
"""

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.tcm_states import TCMAgentState, TCMRouter
from app.agent.components.diagnose.handlers import handle_diagnose_query
from app.agent.intent_recognition.router.intent_router import get_intent_router
from app.agent.conversation_history_db import save_conversation, list_conversations, get_conversation, delete_conversation, get_conversation_stats
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User

logger = logging.getLogger("chat_controller")

router = APIRouter(prefix="/api/v1/chat", tags=["聊天模块"])


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(description="用户消息", min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(default=None, description="会话ID")
    stream: bool = Field(default=True, description="是否流式输出")


@router.post("/generate")
async def chat_generate(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    生成聊天回复 - 支持 SSE 流式输出

    流程：
    1. 意图识别 → 路由
    2. 根据意图调用对应的处理节点
    3. SSE 流式返回结果
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())

    if request.stream:
        return StreamingResponse(
            _stream_chat(request, conversation_id, current_user.id, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # 非流式
    result = await _process_chat(request, conversation_id, current_user.id, db)
    return result


async def _stream_chat(request: ChatRequest, conversation_id: str, user_id: int = None, db: Session = None) -> AsyncGenerator[str, None]:
    """SSE 流式聊天"""
    try:
        # 1. 意图识别
        yield _sse_event("status", {"stage": "intent_recognition", "message": "正在分析您的问题..."})

        intent_router = get_intent_router()
        route_result = await intent_router.route(request.message)
        classification = route_result.classification

        intent_type = classification.primary_intent.value if classification else "general"
        yield _sse_event("intent", {
            "intent": intent_type,
            "confidence": classification.confidence if classification else 0,
            "route_path": route_result.route_path,
        })

        # 2. 根据意图路由
        if intent_type == "diagnosis":
            # 诊断流程
            yield _sse_event("status", {"stage": "diagnosis", "message": "正在进行中医问诊..."})

            state = TCMAgentState(
                messages=[HumanMessage(content=request.message)],
                user_id=str(user_id) if user_id else "anonymous",
                conversation_id=conversation_id,
                user_profile={},
            )

            result = await handle_diagnose_query(state)

            answer = result.get("answer", "抱歉，无法处理您的请求。")
            steps = result.get("steps", [])

            # 保存对话记录
            if user_id and db:
                save_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=request.message,
                    bot_response=answer,
                    intent=intent_type,
                    steps=steps,
                    db=db
                )

            # 流式输出回答（模拟逐字输出）
            yield _sse_event("answer_start", {})
            # 分段发送
            chunk_size = 20
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield _sse_event("answer_chunk", {"content": chunk})

            yield _sse_event("answer_end", {"full_answer": answer, "steps": steps})

        else:
            # 非诊断流程 - 使用 Supervisor
            yield _sse_event("status", {"stage": "general", "message": "正在处理..."})

            from app.agent.supervisor.tcm_supervisor import create_supervisor
            from app.agent.supervisor.specialists import get_all_specialists

            supervisor = create_supervisor()
            for role, executor in get_all_specialists().items():
                supervisor.register_specialist(role, executor)

            result = await supervisor.process(request.message)
            answer = result.get("content", "抱歉，无法处理您的请求。")
            steps = result.get("steps", [])

            # 保存对话记录
            if user_id and db:
                save_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=request.message,
                    bot_response=answer,
                    intent=intent_type,
                    steps=steps,
                    db=db
                )

            yield _sse_event("answer_start", {})
            chunk_size = 20
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield _sse_event("answer_chunk", {"content": chunk})
            yield _sse_event("answer_end", {"full_answer": answer, "steps": steps})

        yield _sse_event("done", {"conversation_id": conversation_id})

    except Exception as e:
        logger.error(f"聊天处理失败: {e}", exc_info=True)
        yield _sse_event("error", {"message": str(e)})


async def _process_chat(request: ChatRequest, conversation_id: str, user_id: int = None, db: Session = None) -> dict:
    """非流式聊天处理"""
    try:
        intent_router = get_intent_router()
        route_result = await intent_router.route(request.message)
        classification = route_result.classification

        intent_type = classification.primary_intent.value if classification else "general"

        if intent_type == "diagnosis":
            state = TCMAgentState(
                messages=[HumanMessage(content=request.message)],
                user_id=str(user_id) if user_id else "anonymous",
                conversation_id=conversation_id,
                user_profile={},
            )
            result = await handle_diagnose_query(state)
            
            # 保存对话记录（数据库版本）
            if user_id and db:
                save_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=request.message,
                    bot_response=result.get("answer", ""),
                    intent=intent_type,
                    steps=result.get("steps", []),
                    db=db
                )
            
            return {
                "conversation_id": conversation_id,
                "intent": intent_type,
                "answer": result.get("answer", ""),
                "steps": result.get("steps", []),
            }
        else:
            from app.agent.supervisor.tcm_supervisor import create_supervisor
            from app.agent.supervisor.specialists import get_all_specialists

            supervisor = create_supervisor()
            for role, executor in get_all_specialists().items():
                supervisor.register_specialist(role, executor)

            result = await supervisor.process(request.message)
            
            # 保存对话记录（数据库版本）
            if user_id and db:
                save_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=request.message,
                    bot_response=result.get("content", ""),
                    intent=intent_type,
                    steps=result.get("steps", []),
                    db=db
                )
            
            return {
                "conversation_id": conversation_id,
                "intent": intent_type,
                "answer": result.get("content", ""),
                "steps": result.get("steps", []),
            }
    except Exception as e:
        logger.error(f"非流式聊天处理失败: {e}", exc_info=True)
        return {
            "conversation_id": conversation_id,
            "intent": "error",
            "answer": f"抱歉，处理您的请求时出现错误：{str(e)}。请稍后重试。",
            "steps": [f"错误: {str(e)}"],
            "error": str(e),
        }


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 对话历史相关接口
@router.get("/history")
async def get_conversation_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """获取对话历史列表（用户隔离）"""
    conversations = list_conversations(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        db=db
    )
    
    return {
        "conversations": conversations,
        "total": len(conversations),
        "limit": limit,
        "offset": offset
    }


@router.get("/history/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话详情（用户隔离）"""
    conversation = get_conversation(conversation_id, user_id=current_user.id, db=db)
    
    if not conversation:
        return {"error": "对话记录不存在", "conversation_id": conversation_id}
    
    return conversation


@router.delete("/history/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除对话记录（用户隔离）"""
    success = delete_conversation(conversation_id, user_id=current_user.id, db=db)
    
    if success:
        return {"message": "对话记录已删除", "conversation_id": conversation_id}
    else:
        return {"error": "删除失败", "conversation_id": conversation_id}


@router.get("/stats")
async def get_chat_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话统计信息（用户隔离）"""
    stats = get_conversation_stats(user_id=current_user.id, db=db)
    return stats


# 医案积累相关接口
@router.get("/cases")
async def get_case_list():
    """获取医案列表（共享）"""
    from app.agent.case_accumulation import get_case_stats
    
    stats = get_case_stats()
    return stats


@router.post("/cases/accumulate")
async def accumulate_case(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从对话中积累医案"""
    from app.agent.case_accumulation import extract_case_from_conversation, save_case
    
    conversation = get_conversation(conversation_id, user_id=current_user.id, db=db)
    if not conversation:
        return {"error": "对话记录不存在"}
    
    case = extract_case_from_conversation(conversation)
    if not case:
        return {"error": "无法从对话中提取医案信息"}
    
    success = save_case(**case)
    
    if success:
        return {"message": "医案已保存", "case": case}
    else:
        return {"error": "保存医案失败"}


@router.get("/cases/similar")
async def find_similar_cases(symptoms: str):
    """查找相似医案（共享）"""
    from app.agent.case_accumulation import find_similar_cases
    
    symptom_list = [s.strip() for s in symptoms.split(",") if s.strip()]
    cases = find_similar_cases(symptom_list)
    
    return {"cases": cases, "symptoms": symptom_list}


# 舌苔分析相关接口
@router.post("/tongue/analyze")
async def analyze_tongue(
    file: bytes,
    current_user: User = Depends(get_current_user)
):
    """分析舌苔图片"""
    from app.agent.tongue_analysis import analyze_tongue_image
    
    if not file:
        return {"error": "请上传图片文件", "status": "failed"}
    
    # 检查文件大小（限制10MB）
    if len(file) > 10 * 1024 * 1024:
        return {"error": "图片文件过大，请上传小于10MB的图片", "status": "failed"}
    
    result = await analyze_tongue_image(file, user_id)
    return result


@router.get("/tongue/history")
async def get_tongue_history(
    user_id: str = "anonymous",
    limit: int = 10
):
    """获取舌象分析历史"""
    from app.agent.tongue_analysis import get_analysis_history
    
    history = get_analysis_history(user_id, limit)
    return {"history": history, "user_id": user_id}
