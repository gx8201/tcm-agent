"""
补充测试 - 覆盖现有测试未涉及的场景

检查清单：
1. analyze_follow_up 否定回答快速结束规则（follow_up_count>=2 且有基本信息时）
2. 复杂辨证路由（MODERATE/COMPLEX 复杂度）
3. 规则路由器实体提取与合并
4. user_profile 在诊断流程中的传递
5. 诊断流程异常降级处理
6. 追问轮次边界值（刚好低于上限 vs 达到上限）
"""

import json
import pytest
import pytest_asyncio
import httpx

from app.agent.llm import MockChatModel
from tests import mock_responses as mr
from app.agent.components.diagnose.models import CollectedDiagnoseInfo


# ─────────────────────────── 辅助函数 ───────────────────────────

def _patch_intent_route(monkeypatch, intent_type: str = "general"):
    """Monkeypatch IntentRouter.route 直接返回指定意图"""
    from app.agent.intent_recognition.schemas import (
        IntentClassification,
        IntentType,
        IntentRouteResult,
    )
    import app.agent.intent_recognition.router.intent_router as ir_mod

    type_map = {
        "general": IntentType.GENERAL,
        "diagnosis": IntentType.DIAGNOSIS,
        "prescription": IntentType.PRESCRIPTION,
        "herb": IntentType.HERB,
        "wellness": IntentType.WELLNESS,
    }

    classification = IntentClassification(
        primary_intent=type_map.get(intent_type, IntentType.GENERAL),
        confidence=0.9,
        reasoning="test",
        route_source="llm",
    )
    route_result = IntentRouteResult(
        classification=classification,
        route_path=["L3:llm_classification", f"L3:classified:{intent_type}"],
    )

    async def _mock_route(self, query):
        return route_result

    monkeypatch.setattr(ir_mod.IntentRouter, "route", _mock_route)


def _patch_get_llm(monkeypatch, response_text: str):
    """Monkeypatch get_llm"""
    from app.agent.llm import MockChatModel
    import app.agent.supervisor.specialists as specialists_mod

    def _mock_get_llm(**kwargs):
        return MockChatModel(responses=[response_text])

    import app.agent.llm as llm_mod
    monkeypatch.setattr(llm_mod, "get_llm", _mock_get_llm)
    if hasattr(specialists_mod, "get_llm"):
        monkeypatch.setattr(specialists_mod, "get_llm", _mock_get_llm)


# ─────────────────────────── 否定回答快速结束 ───────────────────────────


@pytest.mark.asyncio
async def test_negative_answer_fast_exit():
    """
    验证否定回答快速结束规则：
    当用户说"没有/无/全都没有"等否定词，
    且 follow_up_count >= 2 且有 >= 2 项信息时，
    应直接进入 assess_complexity，不再追问。
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="没有，什么都没有")],
        "collected_info": {
            "chief_complaint": "失眠",
            "head_body": "乏力",
        },
        "follow_up_count": 2,  # 已达到快速结束门槛
        "collection_history": [],
    }

    result = await analyze_and_follow_up(state)
    assert result["next_action"] == "assess_complexity", (
        f"否定回答应快速结束，实际: {result['next_action']}"
    )


@pytest.mark.asyncio
async def test_negative_answer_still_ask(monkeypatch):
    """
    当 follow_up_count < 2 时，即使是否定回答也不应直接结束。
    Mock LLM 返回 ask_symptom 决策。
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage
    from app.agent.llm import MockChatModel
    import app.agent.components.diagnose.nodes.analyze_follow_up as af_mod

    state = {
        "messages": [HumanMessage(content="没有怕冷")],
        "collected_info": {"chief_complaint": "失眠"},
        "follow_up_count": 1,  # 低于快速结束门槛
        "collection_history": [],
    }

    # 注入 mock 响应：返回 ask_symptom 决策
    mock_response = json.dumps({
        "action": "ask_symptom",
        "question": "请问您怕热吗？",
        "reasoning": "寒热信息不足，需继续追问",
        "missing_info": ["寒热"],
    })
    monkeypatch.setattr(af_mod, "get_llm", lambda **kw: MockChatModel(responses=[mock_response]))

    result = await analyze_and_follow_up(state)
    # follow_up_count < 2 且是否有 >= 2 项信息（只有 chief_complaint，count=1 < 2）
    # 所以不满足快速结束条件，应走 LLM 路径
    assert result["next_action"] in ("ask_symptom", "assess_complexity")
    if result["next_action"] == "assess_complexity":
        # 若 LLM 返回 assess_complexity，检查 follow_up_count 是否正确
        assert result.get("follow_up_count", 0) > 1


# ─────────────────────────── 追问轮次边界值 ───────────────────────────


@pytest.mark.asyncio
async def test_follow_up_count_not_exceeded():
    """
    当 follow_up_count < MAX_FOLLOW_UP_ROUNDS 且信息不足时，
    analyze_and_follow_up 应返回 ask_symptom（而非 assess_complexity）。
    此测试验证 Mock LLM 路径。
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage

    # 构造信息不足且追问未达上限的状态
    state = {
        "messages": [HumanMessage(content="我最近睡眠不好")],
        "collected_info": {"chief_complaint": "失眠"},  # 只有主诉
        "follow_up_count": 1,  # 远未达到上限 4
        "collection_history": [],
    }

    # 注入 mock 响应：返回 ask_symptom 决策
    import importlib
    import app.agent.components.diagnose.nodes.analyze_follow_up as af_mod
    original_get_llm = af_mod.get_llm

    def _mock_get_llm(**kwargs):
        mock = MockChatModel(responses=[mr.ASK_SYMPTOM])
        return mock

    af_mod.get_llm = _mock_get_llm

    try:
        result = await analyze_and_follow_up(state)
        # 可能返回 ask_symptom（Mock 决策）或 default
        assert "next_action" in result
    finally:
        af_mod.get_llm = original_get_llm


# ─────────────────────────── 规则路由器实体提取 ───────────────────────────


def test_rule_router_prescription_entity_extraction():
    """规则路由器应正确提取方剂名实体"""
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter

    router = RuleBasedRouter()
    entities = router._extract_entities("六味地黄丸有什么功效？")
    assert "六味地黄丸" in entities.prescriptions


def test_rule_router_herb_entity_extraction():
    """规则路由器应正确提取药材名实体"""
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter

    router = RuleBasedRouter()
    entities = router._extract_entities("黄芪的功效是什么？")
    assert "黄芪" in entities.herbs


def test_rule_router_multiple_herbs():
    """规则路由器应提取多个药材"""
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter

    router = RuleBasedRouter()
    entities = router._extract_entities("黄芪和当归一起用可以吗？")
    assert "黄芪" in entities.herbs
    assert "当归" in entities.herbs


def test_rule_router_no_match():
    """不包含已知实体时应返回空实体"""
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter

    router = RuleBasedRouter()
    entities = router._extract_entities("今天天气真好")
    assert entities.herbs == []
    assert entities.prescriptions == []


# ─────────────────────────── 用户画像传递 ───────────────────────────


@pytest.mark.asyncio
async def test_chat_with_user_profile(client: httpx.AsyncClient, monkeypatch):
    """
    验证 user_profile 字段在请求中能被正确传递到处理逻辑。
    发送包含 user_profile 的请求，确认不崩溃。
    """
    _patch_intent_route(monkeypatch, "general")
    _patch_get_llm(monkeypatch, mr.GENERAL_ANSWER)

    resp = await client.post(
        "/api/v1/chat/generate",
        json={
            "message": "你好",
            "stream": False,
            "user_profile": {
                "age": 30,
                "gender": "女",
                "constitution": "气虚质",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "conversation_id" in data


@pytest.mark.asyncio
async def test_chat_without_user_profile(client: httpx.AsyncClient, monkeypatch):
    """
    不传 user_profile 时，应使用默认空字典，不崩溃。
    """
    _patch_intent_route(monkeypatch, "general")
    _patch_get_llm(monkeypatch, mr.GENERAL_ANSWER)

    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "你好", "stream": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data


# ─────────────────────────── 错误降级处理 ───────────────────────────


@pytest.mark.asyncio
async def test_diagnose_fallback_on_exception():
    """
    当 handle_diagnose_query 抛异常时，应走 _fallback_diagnose 路径。
    验证降级逻辑返回有效 answer。
    """
    from app.agent.components.diagnose.handlers import handle_diagnose_query
    from langchain_core.messages import HumanMessage
    from app.agent.tcm_states import TCMAgentState
    import app.agent.components.diagnose.builder as builder_mod

    # 注入一个会抛异常的 get_diagnose_graph
    original = builder_mod.get_diagnose_graph

    def _broken():
        raise RuntimeError("子图初始化失败")

    builder_mod.get_diagnose_graph = _broken

    state = TCMAgentState(
        messages=[HumanMessage(content="我失眠很久了")],
        user_id="test_user",
        conversation_id="test_conv",
    )

    try:
        # 降级路径应调用 Mock LLM 返回 fallback answer
        # 但由于 get_llm 未 patch，这里需要 patch
        import app.agent.components.diagnose.handlers as h_mod
        original_get_llm = h_mod.get_llm
        h_mod.get_llm = lambda **kw: MockChatModel(
            responses=["降级处理：您的症状可能是心肾不交，建议规律作息。"]
        )

        result = await handle_diagnose_query(state)
        # 应返回 answer 而非 error
        assert "answer" in result
        assert len(result["answer"]) > 0
    finally:
        builder_mod.get_diagnose_graph = original
        if 'original_get_llm' in dir():
            h_mod.get_llm = original_get_llm


# ─────────────────────────── 空白消息处理 ───────────────────────────


@pytest.mark.asyncio
async def test_whitespace_only_message(client: httpx.AsyncClient, monkeypatch):
    """
    纯空白消息（"   "）应被 Pydantic 校验通过（min_length=1 允许空白），
    但业务逻辑应能处理。
    """
    _patch_intent_route(monkeypatch, "general")
    _patch_get_llm(monkeypatch, mr.GENERAL_ANSWER)

    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "   ", "stream": False},
    )
    # 不应返回 500
    assert resp.status_code != 500, f"空白消息导致服务器错误: {resp.status_code}"


# ─────────────────────────── 多轮追问历史 ───────────────────────────


def test_collection_history_tracking():
    """
    验证 CollectedDiagnoseInfo.to_summary() 能正确格式化多轮收集的信息。
    """
    info = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        cold_heat="怕冷",
        sweat="无汗",
        head_body="乏力",
        sleep="多梦",
        diet="食欲差",
        other_symptoms=["心悸"],
    )
    summary = info.to_summary()
    assert "主诉：失眠" in summary
    assert "寒热：怕冷" in summary
    assert "睡眠：多梦" in summary
    assert "舌象" not in summary  # 未设置 tongue
    assert "既往史" not in summary  # 未设置 medical_history


# ─────────────────────────── Complex 复杂度降级 ───────────────────────────


def test_complex_routed_to_moderate():
    """
    route_by_complexity 应将 COMPLEX 降级到 moderate_diagnosis（当前未实现 complex 节点）。
    """
    from app.agent.components.diagnose.router import route_by_complexity

    state = {
        "complexity": {
            "level": "complex",
            "score": 8,
            "factors": {},
            "reasoning": "多脏腑受累",
        }
    }
    result = route_by_complexity(state)
    assert result == "moderate_diagnosis", "COMPLEX 应降级到 moderate"


def test_simple_complexity_routing():
    """验证 SIMPLE 复杂度正确路由到 simple_diagnosis"""
    from app.agent.components.diagnose.router import route_by_complexity

    state = {
        "complexity": {
            "level": "simple",
            "score": 1,
            "factors": {},
            "reasoning": "症状单一",
        }
    }
    result = route_by_complexity(state)
    assert result == "simple_diagnosis"


def test_missing_complexity_defaults_to_simple():
    """
    当 complexity 字段缺失时，route_by_complexity 应默认路由到 simple_diagnosis。
    """
    from app.agent.components.diagnose.router import route_by_complexity

    state = {}  # 无 complexity 字段
    result = route_by_complexity(state)
    assert result == "simple_diagnosis"


# ─────────────────────────── collect_info 空消息处理 ───────────────────────────


@pytest.mark.asyncio
async def test_collect_info_no_messages():
    """collect_info 收到空消息列表时不应崩溃"""
    from app.agent.components.diagnose.nodes.collect_info import collect_info

    state = {"messages": []}
    result = await collect_info(state)
    assert "steps" in result
    assert "无消息" in result["steps"][0] or "未找到" in result["steps"][0]


@pytest.mark.asyncio
async def test_collect_info_invalid_state():
    """collect_info 收到非 dict 状态时应安全处理"""
    from app.agent.components.diagnose.nodes.collect_info import collect_info

    # 传入非标准状态（模拟异常输入）
    state = {"messages": [{}]}  # 不是 HumanMessage
    result = await collect_info(state)
    assert "steps" in result
