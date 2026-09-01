"""
意图识别测试

验证 IntentClassifier 在 Mock LLM 下能正确返回各类意图分类结果。
直接传入 MockChatModel 作为 llm 参数，避免 monkeypatch 本地绑定的问题。
"""

import pytest
import pytest_asyncio
import httpx

from app.agent.llm import MockChatModel
from app.agent.intent_recognition.schemas import IntentType
from app.agent.intent_recognition.intent_classifier import IntentClassifier
from tests import mock_responses as mr


@pytest.mark.asyncio
async def test_diagnosis_intent():
    """症状描述 → diagnosis 意图"""
    mock_llm = MockChatModel(responses=[mr.DIAGNOSIS_RESPONSE])
    classifier = IntentClassifier(llm=mock_llm)
    result = await classifier.classify("我最近总是失眠，浑身乏力，食欲也很差")
    assert result.primary_intent == IntentType.DIAGNOSIS
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_prescription_intent():
    """方剂名 → prescription 意图"""
    mock_llm = MockChatModel(responses=[mr.PRESCRIPTION_RESPONSE])
    classifier = IntentClassifier(llm=mock_llm)
    result = await classifier.classify("六味地黄丸有什么功效？")
    assert result.primary_intent == IntentType.PRESCRIPTION
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_herb_intent():
    """中药名 → herb 意图"""
    mock_llm = MockChatModel(responses=[mr.HERB_RESPONSE])
    classifier = IntentClassifier(llm=mock_llm)
    result = await classifier.classify("黄芪的功效与作用是什么？")
    assert result.primary_intent == IntentType.HERB
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_wellness_intent():
    """养生问题 → wellness 意图"""
    mock_llm = MockChatModel(responses=[mr.WELLNESS_RESPONSE])
    classifier = IntentClassifier(llm=mock_llm)
    result = await classifier.classify("春天应该怎么养生？")
    assert result.primary_intent == IntentType.WELLNESS
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_general_intent():
    """基础概念 → general 意图"""
    mock_llm = MockChatModel(responses=[mr.GENERAL_RESPONSE])
    classifier = IntentClassifier(llm=mock_llm)
    result = await classifier.classify("什么是中医？")
    assert result.primary_intent == IntentType.GENERAL
    assert result.confidence >= 0.6
