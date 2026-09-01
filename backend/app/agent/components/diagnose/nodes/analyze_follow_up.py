"""
分析追问节点

分析已收集信息，决定下一步行动
"""

import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from enum import Enum

from ..states import DiagnoseOverallState
from ..models import CollectedDiagnoseInfo
from ..config import diagnose_config
from app.agent.llm import get_llm

logger = logging.getLogger("analyze_follow_up")


class NextAction(str, Enum):
    """下一步行动"""
    ASK_SYMPTOM = "ask_symptom"
    REQUEST_TONGUE = "request_tongue"
    ASSESS_COMPLEXITY = "assess_complexity"
    INTENT_SWITCH = "intent_switch"


class FollowUpDecision(BaseModel):
    """追问决策"""
    action: str = Field(description="下一步行动")
    question: str = Field(default="", description="追问问题")
    reasoning: str = Field(default="", description="决策理由")
    missing_info: list[str] = Field(default_factory=list, description="缺失的信息类别")


FOLLOW_UP_SYSTEM_PROMPT = """你是一位经验丰富的中医师，正在进行问诊。

**你的任务：**
分析已收集的信息，决定下一步行动。

**已收集的信息：**
{collected_summary}

**已追问轮数：** {follow_up_count} / {max_rounds}

**对话历史（最近3轮）：**
{conversation_history}

**决策规则：**
1. 如果主诉不明确，优先追问主诉
2. 如果寒热、汗出、头身、二便、饮食、睡眠这6类信息收集不足4类，继续追问
3. 如果已追问 {max_rounds} 轮或信息足够，进入复杂度评估
4. 避免重复之前已经问过的问题

**请决定下一步行动：**
- ask_symptom: 继续追问症状
- request_tongue: 请求上传舌像
- assess_complexity: 信息足够，进入辨证分析

**用户最新输入：**
{user_input}
"""


async def analyze_and_follow_up(state: DiagnoseOverallState) -> Dict[str, Any]:
    """
    分析已收集信息，决定下一步行动
    """
    try:
        collected_info_dict = state.get("collected_info", {})
        if collected_info_dict:
            collected_info = CollectedDiagnoseInfo(**collected_info_dict)
        else:
            collected_info = CollectedDiagnoseInfo()

        follow_up_count = state.get("follow_up_count", 0)
        max_rounds = diagnose_config.MAX_FOLLOW_UP_ROUNDS

        # 获取用户最新输入
        messages = state.get("messages", [])
        last_user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_message = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        # 规则0: 检测否定回答
        negative_keywords = ["没有", "无", "全都没有", "都没有", "全部没有", "没啥", "没什么"]
        is_negative = any(kw in last_user_message for kw in negative_keywords)

        if is_negative and follow_up_count >= 2 and collected_info.get_filled_count() >= 2:
            return {
                "next_action": NextAction.ASSESS_COMPLEXITY.value,
                "follow_up_count": follow_up_count,
                "steps": ["分析追问: 用户否定回答且已有基本信息，进入评估"],
            }

        # 规则1: 达到最大追问轮数
        if follow_up_count >= max_rounds:
            return {
                "next_action": NextAction.ASSESS_COMPLEXITY.value,
                "follow_up_count": follow_up_count,
                "steps": [f"分析追问: 达到最大轮数，进入复杂度评估"],
            }

        # 规则2: 信息足够
        if collected_info.is_sufficient(min_categories=diagnose_config.MIN_REQUIRED_CATEGORIES):
            return {
                "next_action": NextAction.ASSESS_COMPLEXITY.value,
                "follow_up_count": follow_up_count,
                "steps": ["分析追问: 信息充分，进入复杂度评估"],
            }

        # LLM 决策
        collected_summary = collected_info.to_summary()
        collection_history = state.get("collection_history", [])
        conversation_history = ""
        if collection_history:
            for h in collection_history[-3:]:
                conversation_history += f"第{h['round_number']}轮 - 用户: {h['user_input'][:50]}...\n"
        else:
            conversation_history = "暂无历史"

        system_prompt = FOLLOW_UP_SYSTEM_PROMPT.format(
            collected_summary=collected_summary,
            follow_up_count=follow_up_count,
            max_rounds=max_rounds,
            conversation_history=conversation_history,
            user_input=last_user_message,
        )

        llm = get_llm(temperature=diagnose_config.COLLECTION_TEMPERATURE)
        structured_llm = llm.with_structured_output(FollowUpDecision)

        try:
            decision = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="请分析并决定下一步行动。"),
            ])
        except Exception as parse_err:
            logger.warning(f"FollowUpDecision 解析失败，降级到规则决策: {parse_err}")
            # 解析失败时根据已收集信息做规则降级
            if collected_info.get_filled_count() >= 4:
                return {
                    "next_action": NextAction.ASSESS_COMPLEXITY.value,
                    "follow_up_count": follow_up_count,
                    "steps": [f"分析追问: LLM解析失败，信息已足够，降级到复杂度评估"],
                }
            else:
                return {
                    "next_action": NextAction.ASK_SYMPTOM.value,
                    "follow_up_count": follow_up_count + 1,
                    "follow_up_question": "请再详细描述一下您的症状，比如是否有寒热、出汗、饮食、睡眠等方面的变化？",
                    "answer": "请再详细描述一下您的症状，比如是否有寒热、出汗、饮食、睡眠等方面的变化？",
                    "steps": [f"分析追问: LLM解析失败，信息不足，继续追问"],
                }

        action = decision.action.lower()
        if action not in [a.value for a in NextAction]:
            action = NextAction.ASK_SYMPTOM.value

        result = {
            "next_action": action,
            "follow_up_count": follow_up_count + 1,
            "steps": [f"分析追问: {decision.reasoning}"],
        }

        if action == NextAction.ASK_SYMPTOM.value and decision.question:
            result["follow_up_question"] = decision.question
            result["answer"] = decision.question

        logger.info(f"追问决策: {action}")

        return result

    except Exception as e:
        logger.error(f"分析追问失败: {e}", exc_info=True)
        return {
            "next_action": NextAction.ASSESS_COMPLEXITY.value,
            "steps": [f"分析追问: 失败，降级到复杂度评估 - {str(e)}"],
        }
