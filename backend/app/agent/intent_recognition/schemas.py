"""
意图识别数据模型（精简版）
"""

from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """意图类型"""
    GENERAL = "general"
    WELLNESS = "wellness"
    PRESCRIPTION = "prescription"
    HERB = "herb"
    DIAGNOSIS = "diagnosis"


class SentimentAnalysis(BaseModel):
    """情感分析结果"""
    polarity: Literal["positive", "neutral", "negative"] = "neutral"
    anxiety_score: float = Field(default=0.0, ge=0, le=1)
    urgency: Literal["low", "medium", "high"] = "low"


class ExtractedEntities(BaseModel):
    """提取的中医实体"""
    herbs: list[str] = Field(default_factory=list, description="药材名称")
    prescriptions: list[str] = Field(default_factory=list, description="方剂名称")
    symptoms: list[str] = Field(default_factory=list, description="症状列表")
    body_parts: list[str] = Field(default_factory=list, description="身体部位")
    syndromes: list[str] = Field(default_factory=list, description="证型")
    books: list[str] = Field(default_factory=list, description="古籍名称")


class IntentClassification(BaseModel):
    """意图分类结果"""
    primary_intent: IntentType = Field(description="主要意图类型")
    confidence: float = Field(ge=0, le=1, description="置信度")
    sub_type: Optional[str] = Field(default=None, description="二级分类")
    sentiment: SentimentAnalysis = Field(default_factory=SentimentAnalysis)
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    reasoning: str = Field(default="", description="分类理由")
    suggested_follow_up: Optional[str] = Field(default=None, description="建议追问")
    requires_image: bool = Field(default=False, description="是否需要图片")
    route_source: Literal["rule", "llm"] = Field(default="llm", description="路由来源")


class IntentRouteResult(BaseModel):
    """意图路由结果"""
    classification: Optional[IntentClassification] = None
    route_path: list[str] = Field(default_factory=list)
    latency_ms: float = 0
