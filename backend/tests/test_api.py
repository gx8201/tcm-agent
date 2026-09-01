"""
API 接口测试

覆盖：
- GET /health  健康检查
- POST /api/v1/chat/generate  非流式 / 流式
- 请求体校验（空消息、超长消息、缺少字段）
"""

import json
import pytest
import pytest_asyncio
import httpx

from tests import mock_responses as mr


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
    """
    Monkeypatch get_llm 在所有使用它的模块的本地绑定中。
    包括 supervisor specialists 中的局部 import。
    """
    from app.agent.llm import MockChatModel
    import app.agent.supervisor.specialists as specialists_mod

    def _mock_get_llm(**kwargs):
        return MockChatModel(responses=[response_text])

    # Specialists 在每个 execute 方法中做局部 import，
    # 但 Python 会从 app.agent.llm 模块属性读取。
    # 所以我们需要 patch app.agent.llm.get_llm（模块属性）。
    import app.agent.llm as llm_mod
    monkeypatch.setattr(llm_mod, "get_llm", _mock_get_llm)

    # 同时 patch specialists 模块级别的绑定（如果有）
    # specialists 内部是局部 import，会从 sys.modules 读，
    # 所以 patch 源模块就够了。但为了保险，也 patch 模块级的。
    if hasattr(specialists_mod, "get_llm"):
        monkeypatch.setattr(specialists_mod, "get_llm", _mock_get_llm)


# ─────────────────────────── 健康检查 ───────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient):
    """GET /health 返回 200 且包含 status=healthy"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


# ─────────────────────────── 非流式生成 ───────────────────────────


@pytest.mark.asyncio
async def test_generate_non_stream(client: httpx.AsyncClient, monkeypatch):
    """POST /api/v1/chat/generate stream=false 返回完整 JSON 响应"""
    _patch_intent_route(monkeypatch, "general")
    _patch_get_llm(monkeypatch, mr.GENERAL_ANSWER)

    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "你好，什么是中医？", "stream": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "answer" in data
    assert len(data["answer"]) > 0


# ─────────────────────────── 流式 SSE ───────────────────────────


@pytest.mark.asyncio
async def test_generate_stream_sse(client: httpx.AsyncClient, monkeypatch):
    """POST /api/v1/chat/generate stream=true 返回 SSE 事件流"""
    _patch_intent_route(monkeypatch, "general")
    _patch_get_llm(monkeypatch, mr.GENERAL_ANSWER)

    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "中医是什么？", "stream": True},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # 解析 SSE 事件
    text = resp.text
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = None
        event_data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                event_data = line[len("data:"):].strip()
        if event_name:
            events.append({"event": event_name, "data": event_data})

    event_names = [e["event"] for e in events]
    # 验证 SSE 事件序列
    assert "status" in event_names, f"缺少 status 事件，实际事件: {event_names}"
    assert "intent" in event_names, f"缺少 intent 事件，实际事件: {event_names}"
    assert "answer_start" in event_names
    assert "answer_end" in event_names
    assert "done" in event_names

    # 验证 intent 事件包含正确数据
    intent_event = next(e for e in events if e["event"] == "intent")
    intent_data = json.loads(intent_event["data"])
    assert intent_data["intent"] == "general"


# ─────────────────────────── 请求体校验 ───────────────────────────


@pytest.mark.asyncio
async def test_empty_message(client: httpx.AsyncClient):
    """message="" 应返回 422"""
    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "", "stream": False},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_long_message(client: httpx.AsyncClient):
    """message 超过 2000 字符应返回 422"""
    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "a" * 2001, "stream": False},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_message(client: httpx.AsyncClient):
    """缺少 message 字段应返回 422"""
    resp = await client.post(
        "/api/v1/chat/generate",
        json={"stream": False},
    )
    assert resp.status_code == 422
