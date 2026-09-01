"""
诊断流程测试

覆盖：
- 简单症状诊断的完整流程（collect_info → analyze_follow_up → assess_complexity → simple_diagnosis）
- 追问轮次上限行为
- 信息充足判断逻辑（CollectedDiagnoseInfo.is_sufficient）
"""

import sys
import importlib
import pytest
import pytest_asyncio
import httpx

from app.agent.llm import MockChatModel
from tests import mock_responses as mr


# ─────────────────────────── 辅助函数 ───────────────────────────

# 模块完整路径列表（所有使用了 `from app.agent.llm import get_llm` 的模块）
_MODULES_TO_PATCH = [
    "app.agent.components.diagnose.nodes.collect_info",
    "app.agent.components.diagnose.nodes.analyze_follow_up",
    "app.agent.components.diagnose.nodes.simple_diagnosis",
    "app.agent.components.diagnose.nodes.moderate_diagnosis",
    "app.agent.components.diagnose.handlers",
]


def _get_real_module(dotted_path: str):
    """
    获取真实模块对象。
    用 importlib.import_module 而非 `import X as` 来避免
    __init__.py 中同名 re-export 的遮蔽问题。
    """
    return importlib.import_module(dotted_path)


def _setup_diagnosis_mocks(monkeypatch, mock_responses_list):
    """
    设置诊断流程的 Mock LLM。

    因为各节点用 `from app.agent.llm import get_llm` 做了模块级导入，
    所以需要在每个使用 get_llm 的模块上做 monkeypatch。
    """
    mock_instance = MockChatModel(responses=mock_responses_list)

    def _mock_get_llm(**kwargs):
        return mock_instance

    for mod_path in _MODULES_TO_PATCH:
        mod = _get_real_module(mod_path)
        monkeypatch.setattr(mod, "get_llm", _mock_get_llm)


# ─────────────────────────── 简单诊断流程 ───────────────────────────


@pytest.mark.asyncio
async def test_simple_diagnosis_flow(monkeypatch):
    """
    测试完整诊断流程：
    1. collect_info  → ExtractedInfo (JSON)
    2. analyze_follow_up → FollowUpDecision: assess_complexity (JSON)
    3. assess_complexity → 规则计算（无 LLM 调用）
    4. simple_diagnosis → 辨证回答（纯文本）

    预期：最终 answer 包含诊断关键词。
    """
    # Mock 响应序列（3 次 LLM 调用）
    _setup_diagnosis_mocks(monkeypatch, [
        mr.ROUND1_INFO,            # collect_info: ExtractedInfo
        mr.ASSESS_COMPLEXITY,      # analyze_follow_up: FollowUpDecision → assess_complexity
        mr.SIMPLE_DIAGNOSIS_ANSWER,  # simple_diagnosis: 辨证回答
    ])

    from langchain_core.messages import HumanMessage
    from app.agent.tcm_states import TCMAgentState
    from app.agent.components.diagnose.handlers import handle_diagnose_query

    state = TCMAgentState(
        messages=[HumanMessage(content="我最近总是失眠，浑身乏力，食欲也很差")],
        user_id="test_user",
        conversation_id="test_conv",
    )

    result = await handle_diagnose_query(state)

    assert "answer" in result
    answer = result["answer"]
    assert len(answer) > 0
    # 诊断回答应包含辨证相关关键词
    assert "辨证" in answer or "证" in answer or "四诊" in answer


# ─────────────────────────── 追问轮次上限 ───────────────────────────


@pytest.mark.asyncio
async def test_follow_up_max_rounds(monkeypatch):
    """
    验证追问轮次上限机制：
    当 follow_up_count >= MAX_FOLLOW_UP_ROUNDS(4) 时，
    analyze_and_follow_up 应直接返回 assess_complexity，
    不再调用 LLM 决策。
    """
    from langchain_core.messages import HumanMessage
    from app.agent.components.diagnose.nodes.analyze_follow_up import (
        analyze_and_follow_up,
    )
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo

    # 构造一个已经追问 4 轮的状态
    collected = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        cold_heat="怕冷",
        sweat="无汗",
        head_body="乏力",
        sleep="失眠多梦",
        diet="食欲差",
    )

    state = {
        "messages": [HumanMessage(content="都说了，就是失眠")],
        "collected_info": collected.model_dump(),
        "follow_up_count": 4,  # 已达上限
        "collection_history": [
            {"round_number": 1, "user_input": "失眠", "extracted_info": {}},
            {"round_number": 2, "user_input": "乏力", "extracted_info": {}},
            {"round_number": 3, "user_input": "怕冷", "extracted_info": {}},
            {"round_number": 4, "user_input": "食欲差", "extracted_info": {}},
        ],
    }

    result = await analyze_and_follow_up(state)

    assert result["next_action"] == "assess_complexity"
    # follow_up_count 不应继续增加
    assert result.get("follow_up_count", 4) == 4


# ─────────────────────────── 信息充足判断 ───────────────────────────


def test_info_sufficiency():
    """
    测试 CollectedDiagnoseInfo.is_sufficient() 逻辑。
    当已填充的必要信息类别 >= min_categories 时返回 True。
    """
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo

    # 信息不足（只有 2 项必要信息）
    info_insufficient = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        sleep="失眠多梦",
    )
    assert info_insufficient.is_sufficient(min_categories=4) is False
    assert info_insufficient.get_filled_count() == 2

    # 信息充足（4 项必要信息）
    info_sufficient = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        cold_heat="怕冷",
        sweat="无汗",
        head_body="乏力",
        sleep="失眠多梦",
        diet="食欲差",
    )
    assert info_sufficient.is_sufficient(min_categories=4) is True
    assert info_sufficient.get_filled_count() >= 4


def test_get_missing_categories():
    """测试缺失信息类别识别"""
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo

    info = CollectedDiagnoseInfo(chief_complaint="失眠")
    missing = info.get_missing_categories()
    # 应缺少寒热、汗出、头身、二便、饮食、睡眠
    assert len(missing) == 6
    assert "寒热" in missing
    assert "睡眠" in missing


def test_get_all_symptoms():
    """测试症状汇总"""
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo

    info = CollectedDiagnoseInfo(
        chief_complaint="失眠、乏力",
        sleep="入睡困难",
        diet="食欲差",
        other_symptoms=["心悸", "多梦"],
    )
    symptoms = info.get_all_symptoms()
    assert "失眠、乏力" in symptoms
    assert "入睡困难" in symptoms
    assert "食欲差" in symptoms
    assert "心悸" in symptoms
    assert "多梦" in symptoms


def test_to_summary():
    """测试信息摘要生成"""
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo

    info = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        cold_heat="怕冷",
        sleep="入睡困难",
    )
    summary = info.to_summary()
    assert "主诉：失眠" in summary
    assert "寒热：怕冷" in summary
    assert "睡眠：入睡困难" in summary
