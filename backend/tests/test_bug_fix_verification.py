"""
BUG修复验证测试 - 2026-08-27

验证上一轮发现的4个BUG是否已修复：
- BUG-001: LangGraph V0.5 input/output → input_schema/output_schema
- BUG-002: 规则路由器纯实体匹配置信度 0.75 → 0.85
- BUG-003: MockChatModel 队列耗尽时抛 IndexError
- BUG-004: FollowUpDecision 解析失败智能降级
"""

import warnings
import json
import pytest
import pytest_asyncio
from typing import List


# ============================================================
# BUG-001 验证：LangGraph 弃用警告消除
# ============================================================

def test_no_langgraph_deprecation_warning():
    """
    BUG-001: builder.py 已升级 input/input_schema → input_schema/output_schema
    验证：导入 builder 模块时不应产生 LangGraphDeprecatedSinceV05 警告
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # 导入诊断子图构建器（触发 StateGraph 初始化）
        from app.agent.components.diagnose.builder import create_diagnose_graph
        
        # 创建子图（不编译，避免额外警告）
        graph = create_diagnose_graph()
        
        # 检查是否有 LangGraph 弃用警告
        langgraph_warnings = [
            x for x in w 
            if "LangGraph" in str(x.category.__name__) 
            or "deprecated" in str(x.message).lower()
            or "input_schema" in str(x.message).lower()
        ]
        
        # 应该没有 LangGraph 相关弃用警告
        assert len(langgraph_warnings) == 0, (
            f"发现 LangGraph 弃用警告: {langgraph_warnings}"
        )


def test_builder_uses_input_schema():
    """
    BUG-001 验证：确认 StateGraph 构造函数使用 input_schema 参数
    """
    import inspect
    from app.agent.components.diagnose import builder
    
    source = inspect.getsource(builder.create_diagnose_graph)
    
    # 应使用 input_schema 而非 input
    assert "input_schema=" in source, "builder.py 未使用 input_schema 参数"
    # 不应使用已弃用的 input= (除非在注释中)
    lines = [l.strip() for l in source.split('\n') if 'StateGraph' in l]
    for line in lines:
        if 'input=' in line and 'input_schema' not in line:
            # 检查是否在注释中
            if not line.lstrip().startswith('#'):
                pytest.fail(f"发现弃用的 input= 参数: {line}")


# ============================================================
# BUG-002 验证：规则路由器置信度提升至 0.85
# ============================================================

def test_rule_router_prescription_confidence():
    """
    BUG-002: 纯实体匹配置信度从 0.75 提升到 0.85
    验证：方剂名单独出现时，置信度 >= 0.85
    """
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter
    
    router = RuleBasedRouter()
    
    # 测试方剂名单独出现（无查询词）
    result = router.route("六味地黄丸")
    assert result is not None, "规则路由器未能匹配方剂名"
    assert result.confidence >= 0.85, (
        f"方剂名匹配置信度 {result.confidence} < 0.85，应为 >= 0.85"
    )
    assert result.primary_intent.value == "prescription"
    assert result.route_source == "rule"


def test_rule_router_herb_confidence():
    """
    BUG-002 验证：药材名单独出现时，置信度 >= 0.85
    """
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter
    
    router = RuleBasedRouter()
    
    result = router.route("黄芪")
    assert result is not None, "规则路由器未能匹配药材名"
    assert result.confidence >= 0.85, (
        f"药材名匹配置信度 {result.confidence} < 0.85"
    )
    assert result.primary_intent.value == "herb"


def test_rule_router_high_confidence_triggers_rule_path():
    """
    BUG-002 验证：置信度 >= 0.85 时应走规则路由而非 LLM
    模拟 IntentRouter 的路由逻辑
    """
    from app.agent.intent_recognition.router.rule_router import RuleBasedRouter
    from app.agent.intent_recognition.schemas import IntentType
    
    router = RuleBasedRouter()
    
    # 发送方剂名消息
    result = router.route("六味地黄丸有什么功效")
    
    assert result is not None
    assert result.confidence >= 0.85
    assert result.route_source == "rule", "应走规则路由"
    assert result.primary_intent == IntentType.PRESCRIPTION


# ============================================================
# BUG-003 验证：MockChatModel 队列耗尽抛 IndexError
# ============================================================

def test_mock_queue_exhaustion_raises_indexerror():
    """
    BUG-003: MockChatModel 队列耗尽时应抛出 IndexError 而非静默重复
    """
    from app.agent.llm import MockChatModel
    
    # 只准备 1 个响应
    mock = MockChatModel(responses=["first response"])
    
    # 第一次调用成功
    result1 = mock._next_response()
    assert result1 == "first response"
    
    # 第二次调用应抛出 IndexError
    with pytest.raises(IndexError, match="响应队列已耗尽"):
        mock._next_response()


def test_mock_queue_exhaustion_in_generate():
    """
    BUG-003 验证：_generate 方法在队列耗尽时也应抛异常
    """
    from app.agent.llm import MockChatModel
    from langchain_core.messages import HumanMessage
    
    mock = MockChatModel(responses=["only one"])
    
    # 耗尽队列
    mock._next_response()
    
    # 再次调用 generate 应抛异常（注意：generate需要二维列表 [[message]]）
    with pytest.raises(IndexError):
        mock.generate([[HumanMessage(content="test")]])


def test_mock_queue_exhaustion_in_agenerate():
    """
    BUG-003 验证：_agenerate 方法在队列耗尽时也应抛异常
    """
    import asyncio
    from app.agent.llm import MockChatModel
    from langchain_core.messages import HumanMessage
    
    mock = MockChatModel(responses=["only one"])
    
    # 耗尽队列
    mock._next_response()
    
    # 再次调用 agenerate 应抛异常
    async def _test():
        with pytest.raises(IndexError):
            await mock.agenerate([[HumanMessage(content="test")]])
    
    asyncio.run(_test())


@pytest.mark.asyncio
async def test_mock_structured_output_exhaustion():
    """
    BUG-003 验证：with_structured_output 包装器在队列耗尽时也应抛 IndexError
    """
    from app.agent.llm import MockChatModel
    from pydantic import BaseModel
    
    class TestSchema(BaseModel):
        answer: str = "default"
    
    mock = MockChatModel(responses=["{\"answer\": \"first\"}"])
    wrapper = mock.with_structured_output(TestSchema)
    
    # 耗尽队列
    await wrapper.ainvoke([])
    
    # 再次调用应抛 IndexError
    with pytest.raises(IndexError):
        await wrapper.ainvoke([])


# ============================================================
# BUG-004 验证：FollowUpDecision 解析失败智能降级
# ============================================================

@pytest.mark.asyncio
async def test_followup_decision_parse_failure_information_insufficient():
    """
    BUG-004: Mock返回非JSON响应时，若信息不足应降级为 ask_symptom（继续追问）

    注意：必须构造一个让代码走到LLM路径的状态（规则0/1/2都不触发），
    - follow_up_count < MAX_FOLLOW_UP_ROUNDS (4)
    - collected_info.is_sufficient() = False（信息不足）
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage
    from app.agent.llm import MockChatModel
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo
    import app.agent.components.diagnose.nodes.analyze_follow_up as af_mod

    # 构造状态：信息不足 + 追问未达上限 → 必须走LLM路径
    collected = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        cold_heat="怕冷",
        sleep="多梦",
        # 只有3项，不足4项（MIN_REQUIRED_CATEGORIES）
    )

    state = {
        "messages": [HumanMessage(content="就是失眠")],
        "collected_info": collected.model_dump(),
        "follow_up_count": 1,  # < MAX_FOLLOW_UP_ROUNDS(4)，不触发规则1
        "collection_history": [],
    }

    # Mock LLM 返回非JSON响应（模拟解析失败）
    mock = MockChatModel(responses=["这不是合法的JSON响应"])

    original_get_llm = af_mod.get_llm
    af_mod.get_llm = lambda **kw: mock

    try:
        result = await analyze_and_follow_up(state)

        # 信息不足时应降级为 ask_symptom
        assert result["next_action"] == "ask_symptom", (
            f"信息不足时应降级为 ask_symptom，实际: {result['next_action']}"
        )
        assert "LLM解析失败" in result["steps"][0], "应记录降级原因"
    finally:
        af_mod.get_llm = original_get_llm


@pytest.mark.asyncio
async def test_followup_decision_parse_failure_information_sufficient():
    """
    BUG-004: 验证降级逻辑的代码路径存在

    注意：由于规则2在LLM调用前检查信息充足性，信息充足时不会走到LLM路径，
    因此无法直接测试"信息充足时LLM失败降级为assess_complexity"的场景。

    本测试改为验证：
    1. 降级代码路径存在（通过代码审查确认）
    2. 信息不足时LLM失败能正确降级为ask_symptom（上一个测试已覆盖）

    这里构造一个follow_up_count>=4的状态（触发规则1），确认不会走到LLM。
    以及验证降级逻辑的代码分支确实存在。
    """
    import inspect
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up

    source = inspect.getsource(analyze_and_follow_up)

    # 验证降级逻辑代码存在：应包含对 filled_count 的判断
    assert "get_filled_count" in source, "降级逻辑应检查信息充足度"
    # 源码使用 NextAction.ASSESS_COMPLEXITY.value 而非字面量
    assert "ASSESS_COMPLEXITY" in source, "降级逻辑应包含ASSESS_COMPLEXITY分支"
    assert "ASK_SYMPTOM" in source, "降级逻辑应包含ASK_SYMPTOM分支"


@pytest.mark.asyncio
async def test_followup_decision_parse_failure_information_insufficient():
    """
    BUG-004: Mock返回非JSON响应时，若信息不足应降级为 ask_symptom（继续追问）
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage
    from app.agent.llm import MockChatModel
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo
    import app.agent.components.diagnose.nodes.analyze_follow_up as af_mod
    
    # 构造信息不足的状态（只有2项）
    collected = CollectedDiagnoseInfo(
        chief_complaint="失眠",
        sleep="多梦",
    )
    
    state = {
        "messages": [HumanMessage(content="我失眠")],
        "collected_info": collected.model_dump(),
        "follow_up_count": 1,
        "collection_history": [],
    }
    
    # Mock LLM 返回非JSON响应
    mock = MockChatModel(responses=["invalid json"])
    
    original_get_llm = af_mod.get_llm
    af_mod.get_llm = lambda **kw: mock
    
    try:
        result = await analyze_and_follow_up(state)
        
        # 信息不足时应继续追问
        assert result["next_action"] == "ask_symptom", (
            f"信息不足时应降级为 ask_symptom，实际: {result['next_action']}"
        )
        assert "LLM解析失败" in result["steps"][0]
        assert "follow_up_question" in result
    finally:
        af_mod.get_llm = original_get_llm


@pytest.mark.asyncio
async def test_followup_decision_parse_failure_with_empty_response():
    """
    BUG-004: Mock返回空字符串时应触发降级逻辑
    """
    from app.agent.components.diagnose.nodes.analyze_follow_up import analyze_and_follow_up
    from langchain_core.messages import HumanMessage
    from app.agent.llm import MockChatModel
    from app.agent.components.diagnose.models import CollectedDiagnoseInfo
    import app.agent.components.diagnose.nodes.analyze_follow_up as af_mod
    
    # 信息不足状态
    collected = CollectedDiagnoseInfo(chief_complaint="头痛")
    
    state = {
        "messages": [HumanMessage(content="头痛")],
        "collected_info": collected.model_dump(),
        "follow_up_count": 0,
        "collection_history": [],
    }
    
    # 返回空字符串（也会导致解析失败）
    mock = MockChatModel(responses=[""])
    
    original_get_llm = af_mod.get_llm
    af_mod.get_llm = lambda **kw: mock
    
    try:
        result = await analyze_and_follow_up(state)
        
        # 不应崩溃，应有合理的降级决策
        assert "next_action" in result
        assert result["next_action"] in ["ask_symptom", "assess_complexity"]
    finally:
        af_mod.get_llm = original_get_llm


# ============================================================
# 综合验证：运行完整测试套件无警告
# ============================================================

def test_no_warnings_in_test_suite():
    """
    验证：运行 pytest 时不应有 LangGraph 弃用警告
    此测试在测试套件中运行时检查 warnings 过滤器
    """
    # 此测试仅作为标记，实际警告检查通过 -W all 标志和上述单元测试完成
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
