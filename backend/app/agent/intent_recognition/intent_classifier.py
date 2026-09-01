"""
LLM 意图分类器（精简版）
"""

import logging
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from .schemas import (
    IntentType,
    IntentClassification,
    ExtractedEntities,
    SentimentAnalysis,
)
from app.agent.llm import get_llm

logger = logging.getLogger("intent_classifier")


INTENT_CLASSIFICATION_SYSTEM_PROMPT = """你是一个专业的中医智能助手意图分类器。请准确识别用户问题的意图类型。

## 五大核心意图类型

1. **general**: 中医基础知识科普、理论介绍、闲聊问候
2. **wellness**: 日常养生保健、体质调理、季节养生
3. **prescription**: 中药方剂相关信息查询
4. **herb**: 中药材相关信息查询
5. **diagnosis**: 症状分析、辨证论治的诊疗性问题

## 分类规则

- 如果描述了具体症状，优先归为 diagnosis
- 如果询问药材功效/禁忌，归为 herb
- 如果询问方剂组成/推荐，归为 prescription
- 养生保健类问题归为 wellness
- 中医基础知识归为 general

## 输出要求

请以JSON格式输出，包含：
- primary_intent: 主意图类型
- sub_type: 二级分类
- confidence: 置信度(0-1)
- entities: 提取的实体（symptoms, herbs, prescriptions, syndromes）
- reasoning: 分类理由
"""


class IntentClassifier:
    """LLM 意图分类器"""

    def __init__(self, llm=None):
        self.llm = llm or get_llm(temperature=0.3)

    async def classify(self, query: str) -> IntentClassification:
        """分类用户意图"""
        system_prompt = INTENT_CLASSIFICATION_SYSTEM_PROMPT
        user_prompt = f"请分析以下用户输入：\n\n用户输入: {query}\n\n请输出JSON格式的意图分类结果。"

        llm_with_structure = self.llm.with_structured_output(IntentClassification)

        try:
            result = await llm_with_structure.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            result.route_source = "llm"
            return result
        except Exception as e:
            logger.error(f"意图分类失败: {e}")
            return IntentClassification(
                primary_intent=IntentType.GENERAL,
                confidence=0.3,
                reasoning=f"分类失败，降级处理: {str(e)}",
                route_source="llm",
            )


# 单例
_classifier = None


def get_intent_classifier() -> IntentClassifier:
    """获取意图分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
