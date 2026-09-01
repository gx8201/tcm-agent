"""
诊断子图路由逻辑
"""

from .states import DiagnoseOverallState
from .models import ComplexityLevel
from langgraph.graph import END


def route_collection(state: DiagnoseOverallState) -> str:
    """
    信息收集阶段的路由

    根据 next_action 决定下一步：
    - "ask_symptom": 继续收集信息
    - "assess_complexity": 进入复杂度评估
    - "intent_switch": 退出子图
    """
    next_action = state.get("next_action", "")

    if next_action == "ask_symptom":
        return "collect_info"
    elif next_action in ("request_tongue", "request_report"):
        # 暂时跳过多模态，直接进入评估
        return "assess_complexity"
    elif next_action == "assess_complexity":
        return "assess_complexity"
    elif next_action == "intent_switch":
        return END
    else:
        return "assess_complexity"


def route_by_complexity(state: DiagnoseOverallState) -> str:
    """
    根据复杂度路由到不同的辨证节点
    """
    complexity_dict = state.get("complexity")

    if not complexity_dict:
        return "simple_diagnosis"

    level = complexity_dict.get("level", ComplexityLevel.SIMPLE.value)

    if level == ComplexityLevel.SIMPLE.value:
        return "simple_diagnosis"
    elif level == ComplexityLevel.MODERATE.value:
        return "moderate_diagnosis"
    elif level == ComplexityLevel.COMPLEX.value:
        # 复杂辨证暂时降级到中等
        return "moderate_diagnosis"
    else:
        return "simple_diagnosis"
