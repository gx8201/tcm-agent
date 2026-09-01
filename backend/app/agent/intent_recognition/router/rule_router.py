"""
L1 规则引擎层 - 高频意图快速匹配

使用正则表达式和关键词匹配，快速识别高频确定意图
"""

import re
import logging
from typing import Optional

from ..schemas import (
    IntentClassification,
    IntentType,
    ExtractedEntities,
    SentimentAnalysis,
)

logger = logging.getLogger("rule_router")


class RuleBasedRouter:
    """L1 规则引擎层"""

    # 常见方剂名
    PRESCRIPTION_NAMES = [
        "桂枝汤", "麻黄汤", "小柴胡汤", "四逆汤",
        "六味地黄丸", "金匮肾气丸", "补中益气汤", "四君子汤",
        "四物汤", "八珍汤", "归脾汤", "逍遥散",
        "银翘散", "桑菊饮", "白虎汤",
        "二陈汤", "温胆汤", "半夏泻心汤", "龙胆泻肝汤",
        "酸枣仁汤", "血府逐瘀汤",
    ]

    # 常见药材名
    HERB_NAMES = [
        "黄芪", "人参", "党参", "西洋参", "当归", "熟地", "白芍", "川芎",
        "白术", "茯苓", "甘草", "陈皮", "半夏", "枸杞", "菊花", "金银花",
        "黄连", "黄芩", "黄柏", "栀子", "大黄", "附子", "干姜",
        "肉桂", "桂枝", "麻黄", "柴胡", "葛根", "防风",
        "三七", "丹参", "红花", "桃仁",
        "天麻", "钩藤", "酸枣仁",
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式"""
        prescription_pattern = "|".join(re.escape(p) for p in self.PRESCRIPTION_NAMES)
        herb_pattern = "|".join(re.escape(h) for h in self.HERB_NAMES)

        self._prescription_re = re.compile(f"({prescription_pattern})", re.IGNORECASE)
        self._herb_re = re.compile(f"({herb_pattern})", re.IGNORECASE)

        self._intent_patterns = {
            "prescription_query": [
                re.compile(r"(" + prescription_pattern + r").*?(是什么|介绍|组成|功效|作用)", re.IGNORECASE),
            ],
            "herb_effect": [
                re.compile(r"(" + herb_pattern + r").*?(功效|作用|好处)", re.IGNORECASE),
            ],
            "herb_compatibility": [
                re.compile(r"(" + herb_pattern + r").*?(不能|禁忌|相克|一起)", re.IGNORECASE),
            ],
        }

    def route(self, query: str) -> Optional[IntentClassification]:
        """规则匹配路由"""
        if not query or not query.strip():
            return None

        entities = self._extract_entities(query)
        return self._match_intent(query, entities)

    def _extract_entities(self, query: str) -> ExtractedEntities:
        """提取中医实体"""
        entities = ExtractedEntities()
        prescription_matches = self._prescription_re.findall(query)
        if prescription_matches:
            entities.prescriptions = list(set(prescription_matches))
        herb_matches = self._herb_re.findall(query)
        if herb_matches:
            entities.herbs = list(set(herb_matches))
        return entities

    def _match_intent(self, query: str, entities: ExtractedEntities) -> Optional[IntentClassification]:
        """匹配意图"""
        # 方剂查询
        for pattern in self._intent_patterns["prescription_query"]:
            if pattern.search(query):
                return IntentClassification(
                    primary_intent=IntentType.PRESCRIPTION,
                    confidence=0.95, sub_type="query",
                    entities=entities, reasoning="规则匹配：方剂查询",
                    route_source="rule",
                )

        # 药材配伍
        for pattern in self._intent_patterns["herb_compatibility"]:
            if pattern.search(query):
                return IntentClassification(
                    primary_intent=IntentType.HERB,
                    confidence=0.95, sub_type="compatibility",
                    entities=entities, reasoning="规则匹配：药材配伍",
                    route_source="rule",
                )

        # 药材功效
        for pattern in self._intent_patterns["herb_effect"]:
            if pattern.search(query):
                return IntentClassification(
                    primary_intent=IntentType.HERB,
                    confidence=0.92, sub_type="effect",
                    entities=entities, reasoning="规则匹配：药材功效",
                    route_source="rule",
                )

        # 纯实体匹配
        if entities.prescriptions and not entities.herbs:
            return IntentClassification(
                primary_intent=IntentType.PRESCRIPTION,
                confidence=0.85, sub_type="query",
                entities=entities, reasoning="规则匹配：检测到方剂名",
                route_source="rule",
            )

        if entities.herbs and not entities.prescriptions:
            return IntentClassification(
                primary_intent=IntentType.HERB,
                confidence=0.85, sub_type="effect",
                entities=entities, reasoning="规则匹配：检测到药材名",
                route_source="rule",
            )

        return None


# 单例
_router_instance = None


def get_rule_router() -> RuleBasedRouter:
    """获取规则路由器单例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = RuleBasedRouter()
    return _router_instance
