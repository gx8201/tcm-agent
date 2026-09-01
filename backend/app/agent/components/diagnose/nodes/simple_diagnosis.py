"""
简单辨证节点

简单病情的直接辨证（LLM 直接分析）
"""

import logging
from typing import Dict, Any
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from ..states import DiagnoseOverallState
from ..models import CollectedDiagnoseInfo
from ..config import diagnose_config
from ..prompts import SIMPLE_DIAGNOSIS_PROMPT
from app.agent.llm import get_llm

logger = logging.getLogger("simple_diagnosis")


def _get_current_solar_term() -> str:
    """获取当前节气（简化版）"""
    now = datetime.now()
    solar_terms = {
        1: "小寒/大寒", 2: "立春/雨水", 3: "惊蛰/春分",
        4: "清明/谷雨", 5: "立夏/小满", 6: "芒种/夏至",
        7: "小暑/大暑", 8: "立秋/处暑", 9: "白露/秋分",
        10: "寒露/霜降", 11: "立冬/小雪", 12: "大雪/冬至"
    }
    return solar_terms.get(now.month, "未知节气")


def _format_user_profile(profile: Dict[str, Any]) -> str:
    """格式化用户画像"""
    if not profile:
        return "暂无用户健康档案"
    parts = []
    if profile.get("gender"):
        parts.append(f"性别：{profile['gender']}")
    if profile.get("age") or profile.get("age_group"):
        parts.append(f"年龄：{profile.get('age') or profile.get('age_group')}")
    if profile.get("constitution"):
        parts.append(f"体质类型：{profile['constitution']}")
    if profile.get("chronic_conditions"):
        conditions = profile["chronic_conditions"]
        if isinstance(conditions, list):
            parts.append(f"既往病史：{', '.join(conditions)}")
        else:
            parts.append(f"既往病史：{conditions}")
    return "\n".join(parts) if parts else "暂无用户健康档案"


async def simple_diagnosis(state: DiagnoseOverallState) -> Dict[str, Any]:
    """
    简单病情的直接辨证

    适用场景：
    - 单一证型（如普通感冒）
    - 症状明确，指向清晰
    - 无复杂既往史
    """
    try:
        # 获取已收集的信息
        collected_info_dict = state.get("collected_info", {})
        if collected_info_dict:
            collected_info = CollectedDiagnoseInfo(**collected_info_dict)
            collected_summary = collected_info.to_summary()
        else:
            collected_summary = "暂无详细信息"

        # 获取舌像分析
        tongue_analysis = state.get("tongue_analysis")
        tongue_desc = "未提供"
        if tongue_analysis:
            parts = []
            for key, name in [("tongue_color", "舌色"), ("tongue_shape", "舌形"),
                               ("coating_color", "苔色"), ("coating_quality", "苔质")]:
                if tongue_analysis.get(key):
                    parts.append(f"{name}：{tongue_analysis[key]}")
            tongue_desc = "\n".join(parts) if parts else "未提供"

        user_profile = state.get("user_profile", {})
        user_profile_desc = _format_user_profile(user_profile)
        solar_term = _get_current_solar_term()

        # 构建提示词
        prompt = SIMPLE_DIAGNOSIS_PROMPT.format(
            collected_info=collected_summary,
            tongue_analysis=tongue_desc,
            user_profile=user_profile_desc,
            solar_term=solar_term,
        )

        # 调用 LLM
        llm = get_llm(temperature=diagnose_config.DIAGNOSIS_TEMPERATURE)
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="请开始您的辨证分析。")
        ])

        answer = response.content
        logger.info("简单辨证完成")

        return {
            "answer": answer,
            "steps": ["简单辨证: 完成"],
        }

    except Exception as e:
        logger.error(f"简单辨证失败: {e}", exc_info=True)
        return {
            "answer": f"抱歉，辨证分析过程中出现错误：{str(e)}。建议您前往医院进行详细检查。",
            "steps": [f"简单辨证: 失败 - {str(e)}"],
        }
