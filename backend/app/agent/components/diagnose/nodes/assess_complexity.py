"""
复杂度评估节点

评估病情复杂度，决定辨证策略
"""

import logging
import re
from typing import Dict, Any

from ..states import DiagnoseOverallState
from ..models import CollectedDiagnoseInfo, ComplexityAssessment, ComplexityLevel
from ..config import diagnose_config

logger = logging.getLogger("assess_complexity")


# 脏腑关键词映射
ORGAN_KEYWORDS = {
    "心": ["心悸", "心慌", "失眠", "多梦", "健忘", "胸闷"],
    "肝": ["头晕", "头痛", "烦躁", "易怒", "胁痛", "目眩"],
    "脾": ["食欲不振", "腹胀", "便溏", "乏力", "肢体困重"],
    "肺": ["咳嗽", "气短", "呼吸", "鼻塞", "流涕"],
    "肾": ["腰痛", "耳鸣", "遗精", "尿频", "夜尿", "怕冷"],
}


async def assess_complexity(state: DiagnoseOverallState) -> Dict[str, Any]:
    """
    评估病情复杂度，决定辨证策略

    评估因素（总分 10 分）：
    - 症状数量: 0-2
    - 涉及脏腑: 0-2
    - 病程: 0-2
    - 症状矛盾: 0-2
    - 既往慢性病: 0-2
    """
    try:
        collected_info_dict = state.get("collected_info", {})
        if not collected_info_dict:
            complexity = ComplexityAssessment(
                level=ComplexityLevel.SIMPLE, score=0, factors={},
                reasoning="未收集到足够信息，默认简单处理"
            )
            return {
                "complexity": complexity.model_dump(),
                "next_action": "simple",
                "steps": ["复杂度评估: 简单 (0分)"],
            }

        collected_info = CollectedDiagnoseInfo(**collected_info_dict)
        score = 0
        factors = {}

        # 因素1: 症状数量
        symptoms = collected_info.get_all_symptoms()
        symptom_count = len([s for s in symptoms if s])
        if symptom_count <= 3:
            factors["symptom_count"] = 0
        elif symptom_count <= 5:
            factors["symptom_count"] = 1
        else:
            factors["symptom_count"] = 2
        score += factors["symptom_count"]

        # 因素2: 涉及脏腑
        involved_organs = _identify_organs(collected_info)
        organ_count = len(involved_organs)
        if organ_count <= 1:
            factors["organ_systems"] = 0
        elif organ_count == 2:
            factors["organ_systems"] = 1
        else:
            factors["organ_systems"] = 2
        score += factors["organ_systems"]

        # 因素3: 病程
        duration_score = _assess_duration(collected_info.duration)
        factors["duration"] = duration_score
        score += duration_score

        # 因素4: 症状矛盾
        has_contradiction = _check_contradiction(collected_info)
        factors["contradiction"] = 2 if has_contradiction else 0
        score += factors["contradiction"]

        # 因素5: 既往慢性病
        chronic_count = len(collected_info.medical_history or [])
        if chronic_count == 0:
            factors["chronic_conditions"] = 0
        elif chronic_count <= 2:
            factors["chronic_conditions"] = 1
        else:
            factors["chronic_conditions"] = 2
        score += factors["chronic_conditions"]

        # 确定复杂度级别
        if score <= diagnose_config.SIMPLE_THRESHOLD:
            level = ComplexityLevel.SIMPLE
            next_action = "simple"
        elif score <= diagnose_config.MODERATE_THRESHOLD:
            level = ComplexityLevel.MODERATE
            next_action = "moderate"
        else:
            level = ComplexityLevel.COMPLEX
            next_action = "complex"

        reasoning = _generate_reasoning(factors, symptom_count, organ_count, involved_organs)

        complexity = ComplexityAssessment(
            level=level, score=score, factors=factors, reasoning=reasoning
        )

        logger.info(f"复杂度评估完成: {level.value} ({score}分)")

        return {
            "complexity": complexity.model_dump(),
            "next_action": next_action,
            "steps": [f"复杂度评估: {level.value} ({score}分) - {reasoning}"],
        }

    except Exception as e:
        logger.error(f"复杂度评估失败: {e}", exc_info=True)
        complexity = ComplexityAssessment(
            level=ComplexityLevel.SIMPLE, score=0, factors={},
            reasoning=f"评估失败，默认简单处理: {str(e)}"
        )
        return {
            "complexity": complexity.model_dump(),
            "next_action": "simple",
            "steps": [f"复杂度评估: 失败，降级到简单 - {str(e)}"],
        }


def _identify_organs(collected_info: CollectedDiagnoseInfo) -> list[str]:
    """识别涉及的脏腑"""
    all_text = collected_info.to_summary().lower()
    involved = []
    for organ, keywords in ORGAN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in all_text:
                if organ not in involved:
                    involved.append(organ)
                break
    return involved


def _assess_duration(duration: str | None) -> int:
    """评估病程得分"""
    if not duration:
        return 0
    duration_lower = duration.lower()
    long_term_keywords = ["年", "月", "慢性", "长期", "反复"]
    for keyword in long_term_keywords:
        if keyword in duration_lower:
            if "年" in duration_lower or "慢性" in duration_lower:
                return 2
            if "月" in duration_lower:
                match = re.search(r'(\d+)\s*月', duration_lower)
                if match:
                    months = int(match.group(1))
                    return 2 if months >= 3 else 1
                return 1
            return 1
    return 0


def _check_contradiction(collected_info: CollectedDiagnoseInfo) -> bool:
    """检查症状是否矛盾"""
    if collected_info.cold_heat:
        ch = collected_info.cold_heat.lower()
        has_cold = any(k in ch for k in ["怕冷", "恶寒", "畏寒"])
        has_heat = any(k in ch for k in ["发热", "怕热", "烦热"])
        if has_cold and has_heat:
            return True
    has_fatigue = collected_info.head_body and "乏力" in collected_info.head_body
    has_irritability = collected_info.emotion and "烦躁" in collected_info.emotion
    if has_fatigue and has_irritability:
        return True
    return False


def _generate_reasoning(factors: Dict[str, int], symptom_count: int,
                        organ_count: int, organs: list[str]) -> str:
    """生成评估理由"""
    parts = []
    if factors.get("symptom_count", 0) > 0:
        parts.append(f"症状较多({symptom_count}个)")
    if factors.get("organ_systems", 0) > 0:
        organs_str = "、".join(organs) if organs else "多个"
        parts.append(f"涉及{organs_str}脏腑")
    if factors.get("duration", 0) > 0:
        parts.append("病程较长" if factors["duration"] == 2 else "病程中等")
    if factors.get("contradiction", 0) > 0:
        parts.append("症状存在矛盾")
    if factors.get("chronic_conditions", 0) > 0:
        parts.append("有既往病史")
    return "、".join(parts) if parts else "症状单一明确"
