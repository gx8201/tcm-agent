"""
意图路由主入口（精简版）

L1: 规则层 - 高频快速匹配
L3: LLM层 - 深度分类
"""

import time
import logging
from typing import Optional

from .rule_router import get_rule_router
from ..intent_classifier import get_intent_classifier
from ..schemas import (
    IntentRouteResult,
    IntentClassification,
    IntentType,
)

logger = logging.getLogger("intent_router")


class IntentRouter:
    """意图路由器（精简版）"""

    OOS_CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, rule_router=None, intent_classifier=None):
        self.rule_router = rule_router or get_rule_router()
        self.intent_classifier = intent_classifier or get_intent_classifier()

    async def route(self, query: str) -> IntentRouteResult:
        """
        执行意图路由

        Args:
            query: 用户输入

        Returns:
            IntentRouteResult: 路由结果
        """
        start_time = time.time()
        route_path = []
        result = IntentRouteResult()

        # L1: 规则层匹配
        route_path.append("L1:rule_matching")
        rule_result = self.rule_router.route(query)

        if rule_result and rule_result.confidence >= 0.85:
            route_path.append(f"L1:matched:{rule_result.primary_intent.value}")
            result.classification = rule_result
            result.route_path = route_path
            result.latency_ms = (time.time() - start_time) * 1000
            return result

        # L3: LLM 分类
        route_path.append("L3:llm_classification")
        llm_result = await self.intent_classifier.classify(query)
        route_path.append(f"L3:classified:{llm_result.primary_intent.value}")

        # 合并规则层实体
        if rule_result and rule_result.entities:
            merged_herbs = list(set(rule_result.entities.herbs + llm_result.entities.herbs))
            merged_prescriptions = list(set(rule_result.entities.prescriptions + llm_result.entities.prescriptions))
            llm_result.entities.herbs = merged_herbs
            llm_result.entities.prescriptions = merged_prescriptions

        result.classification = llm_result
        result.route_path = route_path
        result.latency_ms = (time.time() - start_time) * 1000

        return result


# 单例
_router = None


def get_intent_router() -> IntentRouter:
    """获取意图路由器单例"""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
