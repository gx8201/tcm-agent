"""
边界条件测试

覆盖：
- 空消息返回 422
- 超长消息返回 422
- 特殊字符处理
- 并发请求
"""

import asyncio
import pytest
import pytest_asyncio
import httpx

from tests import mock_responses as mr


# ─────────────────────────── 辅助函数 ───────────────────────────


def _patch_for_general(monkeypatch):
    """快速 patch 意图路由和 LLM 为 general 模式"""
    from app.agent.intent_recognition.schemas import (
        IntentClassification,
        IntentType,
        IntentRouteResult,
    )
    from app.agent.llm import MockChatModel
    import app.agent.intent_recognition.router.intent_router as ir_mod
    import app.agent.llm as llm_mod

    classification = IntentClassification(
        primary_intent=IntentType.GENERAL,
        confidence=0.8,
        reasoning="test",
        route_source="llm",
    )
    route_result = IntentRouteResult(
        classification=classification,
        route_path=["L3:llm_classification"],
    )

    async def _mock_route(self, query):
        await asyncio.sleep(0.01)
        return route_result

    monkeypatch.setattr(ir_mod.IntentRouter, "route", _mock_route)

    def _mock_get_llm(**kwargs):
        return MockChatModel(responses=[mr.GENERAL_ANSWER])

    monkeypatch.setattr(llm_mod, "get_llm", _mock_get_llm)


# ─────────────────────────── 基本校验 ───────────────────────────


@pytest.mark.asyncio
async def test_empty_message_returns_422(client: httpx.AsyncClient):
    """空消息应返回 422 Unprocessable Entity"""
    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "", "stream": False},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_long_message_returns_422(client: httpx.AsyncClient):
    """超过 2000 字符的消息应返回 422"""
    resp = await client.post(
        "/api/v1/chat/generate",
        json={"message": "好" * 2001, "stream": False},
    )
    assert resp.status_code == 422


# ─────────────────────────── 特殊字符 ───────────────────────────


@pytest.mark.asyncio
async def test_special_characters(client: httpx.AsyncClient, monkeypatch):
    """消息中包含特殊字符（emoji、HTML、SQL）不导致崩溃"""
    _patch_for_general(monkeypatch)

    special_messages = [
        "中医🔥💊有什么功效？",
        "<script>alert('xss')</script>",
        "'; DROP TABLE users; --",
        "什么是\n\t中医？",
        "   ",
    ]

    for msg in special_messages:
        resp = await client.post(
            "/api/v1/chat/generate",
            json={"message": msg, "stream": False},
        )
        # 只要不返回 500 就算通过
        # 空白消息（"   "）可能被 Pydantic 接受或拒绝，都是合理的
        assert resp.status_code in (200, 422), (
            f"消息 {msg!r} 导致异常状态码 {resp.status_code}"
        )


# ─────────────────────────── 并发请求 ───────────────────────────


@pytest.mark.asyncio
async def test_concurrent_requests(client: httpx.AsyncClient, monkeypatch):
    """多个并发请求不应互相干扰"""
    _patch_for_general(monkeypatch)

    # 发送 5 个并发请求
    messages = [f"问题{i}：什么是中医？" for i in range(5)]

    async def _send(msg):
        return await client.post(
            "/api/v1/chat/generate",
            json={"message": msg, "stream": False},
        )

    results = await asyncio.gather(*[_send(m) for m in messages])

    for i, resp in enumerate(results):
        assert resp.status_code == 200, f"并发请求 {i} 失败: {resp.status_code}"
        data = resp.json()
        assert "answer" in data
        assert "conversation_id" in data
        assert len(data["answer"]) > 0
