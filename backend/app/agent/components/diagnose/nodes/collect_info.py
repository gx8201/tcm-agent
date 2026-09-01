"""
信息收集节点

从用户输入中提取症状信息，更新 collected_info
"""

import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..states import DiagnoseOverallState
from ..models import CollectedDiagnoseInfo
from app.agent.llm import get_llm

logger = logging.getLogger("collect_info")


class ExtractedInfo(BaseModel):
    """从用户输入中提取的信息"""
    chief_complaint: str = Field(default="", description="主诉症状")
    onset_time: str = Field(default="", description="发病时间")
    duration: str = Field(default="", description="病程")
    cold_heat: str = Field(default="", description="寒热情况")
    sweat: str = Field(default="", description="汗出情况")
    head_body: str = Field(default="", description="头身症状")
    urine_stool: str = Field(default="", description="二便情况")
    diet: str = Field(default="", description="饮食情况")
    chest_abdomen: str = Field(default="", description="胸腹症状")
    sleep: str = Field(default="", description="睡眠情况")
    emotion: str = Field(default="", description="情志状态")
    complexion: str = Field(default="", description="面色")
    other_symptoms: list[str] = Field(default_factory=list, description="其他症状")


COLLECTION_SYSTEM_PROMPT = """你是一位经验丰富的中医师，正在进行问诊。

你的任务是从患者的描述中提取关键信息，按照中医十问的框架进行分类。

**中医十问框架：**
1. 寒热：恶寒、发热、寒热往来
2. 汗出：有汗、无汗、盗汗、自汗
3. 头身：头痛、头晕、身痛、乏力
4. 二便：大便（便秘、腹泻）、小便（频数、不利）
5. 饮食：食欲、口渴、口苦、口淡
6. 胸腹：胸闷、腹胀、心悸
7. 睡眠：失眠、多梦、嗜睡
8. 情志：烦躁、抑郁、焦虑

**已收集的信息：**
{collected_summary}

**患者本轮描述：**
{user_input}

请提取本轮新增的信息。
"""


async def collect_info(state: DiagnoseOverallState) -> Dict[str, Any]:
    """
    收集用户输入的信息，更新 collected_info

    功能：
    1. 解析用户最新输入
    2. 提取症状、时间、程度等信息
    3. 映射到 CollectedDiagnoseInfo 的相应字段
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            return {"steps": ["信息收集: 无消息"]}

        # 获取最后一条用户消息
        last_user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_message = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        if not last_user_message:
            return {"steps": ["信息收集: 未找到用户消息"]}

        # 获取已收集的信息
        collected_info_dict = state.get("collected_info", {})
        if collected_info_dict:
            collected_info = CollectedDiagnoseInfo(**collected_info_dict)
        else:
            collected_info = CollectedDiagnoseInfo()

        # 构建提示词
        collected_summary = collected_info.to_summary() if collected_info.get_filled_count() > 0 else "暂无"
        system_prompt = COLLECTION_SYSTEM_PROMPT.format(
            collected_summary=collected_summary,
            user_input=last_user_message
        )

        # 调用 LLM 提取信息
        llm = get_llm(temperature=0.7)
        structured_llm = llm.with_structured_output(ExtractedInfo)

        response = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=last_user_message)
        ])

        # 更新 collected_info
        if response.chief_complaint and not collected_info.chief_complaint:
            collected_info.chief_complaint = response.chief_complaint
        if response.onset_time and not collected_info.onset_time:
            collected_info.onset_time = response.onset_time
        if response.duration and not collected_info.duration:
            collected_info.duration = response.duration

        # 更新十问信息（追加而不是覆盖）
        for field in ["cold_heat", "sweat", "head_body", "urine_stool",
                       "diet", "chest_abdomen", "sleep", "emotion", "complexion"]:
            new_val = getattr(response, field, "")
            if new_val:
                existing = getattr(collected_info, field)
                if not existing:
                    setattr(collected_info, field, new_val)
                elif new_val not in existing:
                    setattr(collected_info, field, f"{existing}；{new_val}")

        # 更新其他症状
        if response.other_symptoms:
            if collected_info.other_symptoms is None:
                collected_info.other_symptoms = []
            for symptom in response.other_symptoms:
                if symptom not in collected_info.other_symptoms:
                    collected_info.other_symptoms.append(symptom)

        # 记录收集历史
        collection_history = state.get("collection_history", [])
        collection_history.append({
            "round_number": len(collection_history) + 1,
            "user_input": last_user_message,
            "extracted_info": response.model_dump(),
        })

        logger.info(f"信息收集完成，已收集 {collected_info.get_filled_count()} 类信息")

        return {
            "collected_info": collected_info.model_dump(),
            "collection_history": collection_history,
            "steps": [f"信息收集: 提取了 {len([f for f in response.model_dump().values() if f])} 项信息"],
        }

    except Exception as e:
        logger.error(f"信息收集失败: {e}", exc_info=True)
        return {"steps": [f"信息收集: 失败 - {str(e)}"]}
