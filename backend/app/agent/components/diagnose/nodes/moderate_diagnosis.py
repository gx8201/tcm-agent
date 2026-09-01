"""
中等辨证节点

中等复杂度的 RAG 辅助辨证
精简版：使用模拟的 RAG 检索结果（实际版本需要连接知识图谱和向量数据库）
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from ..states import DiagnoseOverallState
from ..models import CollectedDiagnoseInfo
from ..config import diagnose_config
from ..prompts import MODERATE_DIAGNOSIS_PROMPT
from app.agent.llm import get_llm

logger = logging.getLogger("moderate_diagnosis")


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


async def moderate_diagnosis(state: DiagnoseOverallState) -> Dict[str, Any]:
    """
    中等复杂度的 RAG 辅助辨证

    适用场景：
    - 多个症状需要综合判断
    - 可能存在兼证
    - 需要医案参考

    精简版：使用 LLM 直接生成辨证结果，不依赖外部知识图谱
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

        # 获取用户画像
        user_profile = state.get("user_profile", {})
        user_profile_desc = _format_user_profile(user_profile)

        # 模拟 RAG 检索结果（实际版本需要连接知识图谱）
        symptoms = collected_info.get_all_symptoms()
        similar_syndromes = _mock_syndrome_search(symptoms)
        similar_cases = _mock_case_search(symptoms)
        related_prescriptions = _mock_prescription_search(symptoms)

        solar_term = _get_current_solar_term()

        # 构建提示词
        prompt = MODERATE_DIAGNOSIS_PROMPT.format(
            collected_info=collected_summary,
            tongue_analysis=tongue_desc,
            user_profile=user_profile_desc,
            syndrome_matches=_format_syndromes(similar_syndromes),
            similar_cases=_format_cases(similar_cases),
            related_prescriptions=_format_prescriptions(related_prescriptions),
        )

        # 调用 LLM
        llm = get_llm(temperature=diagnose_config.DIAGNOSIS_TEMPERATURE)
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="请结合参考资料开始您的辨证分析。")
        ])

        answer = response.content
        logger.info("中等辨证完成")

        return {
            "answer": answer,
            "steps": ["中等辨证: 完成（含参考资料）"],
        }

    except Exception as e:
        logger.error(f"中等辨证失败: {e}", exc_info=True)
        return {
            "answer": f"抱歉，辨证分析过程中出现错误：{str(e)}。建议您前往医院进行详细检查。",
            "steps": [f"中等辨证: 失败 - {str(e)}"],
        }


def _mock_syndrome_search(symptoms: List[str]) -> List[Dict[str, Any]]:
    """模拟证型搜索（实际应连接知识图谱）"""
    return [
        {"name": "气虚证", "symptoms": ["乏力", "气短", "自汗"], "similarity": 0.8},
        {"name": "脾气虚证", "symptoms": ["乏力", "食欲不振", "便溏"], "similarity": 0.7},
    ]


def _mock_case_search(symptoms: List[str]) -> List[Dict[str, Any]]:
    """模拟医案搜索（实际应连接向量数据库）"""
    return [
        {
            "case_id": "case_001",
            "chief_complaint": "乏力、食欲不振",
            "syndrome": "脾气虚证",
            "treatment": "补中益气汤加减",
            "similarity": 0.75,
        },
    ]


def _mock_prescription_search(symptoms: List[str]) -> List[Dict[str, Any]]:
    """模拟方剂搜索（实际应连接知识图谱）"""
    return [
        {
            "name": "补中益气汤",
            "indication": "脾胃气虚",
            "composition": ["黄芪", "人参", "白术", "甘草"],
        },
    ]


def _format_syndromes(syndromes: List[Dict[str, Any]]) -> str:
    """格式化证型列表"""
    if not syndromes:
        return "暂无相似证型"
    parts = []
    for i, s in enumerate(syndromes[:3], 1):
        symptoms_str = "、".join(s.get("symptoms", []))
        parts.append(f"{i}. {s['name']} (相似度: {s.get('similarity', 0):.0%})\n   主要症状：{symptoms_str}")
    return "\n".join(parts)


def _format_cases(cases: List[Dict[str, Any]]) -> str:
    """格式化医案列表"""
    if not cases:
        return "暂无相似医案"
    parts = []
    for i, c in enumerate(cases[:2], 1):
        parts.append(
            f"{i}. 主诉：{c.get('chief_complaint', '未知')}\n"
            f"   证型：{c.get('syndrome', '未知')}\n"
            f"   治疗：{c.get('treatment', '未知')}"
        )
    return "\n".join(parts)


def _format_prescriptions(prescriptions: List[Dict[str, Any]]) -> str:
    """格式化方剂列表"""
    if not prescriptions:
        return "暂无相关方剂"
    parts = []
    for i, p in enumerate(prescriptions[:3], 1):
        composition = p.get("composition", [])
        composition_str = "、".join(composition[:5])
        parts.append(
            f"{i}. {p['name']}\n"
            f"   主治：{p.get('indication', '未知')}\n"
            f"   组成：{composition_str}等"
        )
    return "\n".join(parts)


def _format_user_profile(user_profile: Dict[str, Any]) -> str:
    """格式化用户画像"""
    if not user_profile:
        return "暂无用户画像"
    parts = []
    if user_profile.get("age"):
        parts.append(f"年龄：{user_profile['age']}岁")
    if user_profile.get("gender"):
        parts.append(f"性别：{user_profile['gender']}")
    if user_profile.get("constitution"):
        parts.append(f"体质：{user_profile['constitution']}")
    return "\n".join(parts) if parts else "暂无用户画像"
