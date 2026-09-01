"""
TCM 全局状态定义

定义中医多智能体系统的核心状态结构
精简版：去除中间件、知识图谱等复杂状态
"""

from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


# ============== 消息处理函数 ==============

def reduce_str(left: str | None, right: str | None) -> str:
    """字符串归约：右值覆盖左值"""
    if right is not None:
        return right
    return left or ""


def reduce_list(left: list | None, right: list | None) -> list:
    """列表归约：合并两个列表"""
    left = left or []
    right = right or []
    return left + right


# ============== 路由类型定义 ==============

TCMQueryType = Literal[
    "tcm-chat",          # 中医闲聊
    "tcm-wellness",      # 中医养生
    "tcm-diagnose",      # 辨证问诊
    "tcm-prescription",  # 方剂推荐
    "tcm-herb",          # 药材咨询
    "additional-info",   # 需要更多信息
]


# ============== 意图分类结果 ==============

class IntentClassification(BaseModel):
    """意图分类结果（简化版）"""
    primary_intent: str = Field(description="主要意图类型")
    confidence: float = Field(default=0.5, ge=0, le=1, description="置信度")
    sub_type: Optional[str] = Field(default=None, description="二级分类")
    entities: dict = Field(default_factory=dict, description="提取的实体")
    reasoning: str = Field(default="", description="分类理由")


class TCMRouter(BaseModel):
    """中医意图路由结果"""
    classification: Optional[IntentClassification] = Field(
        default=None, description="意图分类结果"
    )
    query_type: TCMQueryType = Field(description="查询类型")
    reasoning: str = Field(default="", description="路由推理")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度")
    extracted_entities: dict = Field(default_factory=dict, description="提取的实体")


# ============== 模型配置 ==============

class LLMConfig(BaseModel):
    """LLM 模型配置"""
    model_name: str = Field(default="deepseek-chat", description="模型名称")
    api_key: str = Field(default="", description="API Key")
    base_url: Optional[str] = Field(default=None, description="API Base URL")
    temperature: float = Field(default=0.7, description="温度参数")
    max_tokens: int = Field(default=4096, description="最大 token 数")


# ============== 辨证结果 ==============

class SyndromeResult(BaseModel):
    """辨证结果"""
    syndrome_name: str = Field(description="证型名称")
    confidence: float = Field(ge=0.0, le=1.0, description="辨证置信度")
    symptoms_matched: list[str] = Field(default_factory=list, description="匹配的症状")
    treatment_principle: str = Field(default="", description="治则治法")
    recommended_prescriptions: list[str] = Field(default_factory=list, description="推荐方剂")


# ============== 主状态定义 ==============

class TCMInputState(BaseModel):
    """中医智能体输入状态"""
    messages: Annotated[list[AnyMessage], add_messages] = Field(
        default_factory=list, description="对话消息历史"
    )
    user_id: str = Field(default="", description="用户ID")
    conversation_id: str = Field(default="", description="会话ID")
    user_profile: dict = Field(default_factory=dict, description="用户画像")
    llm_config: Optional[LLMConfig] = Field(default=None, description="LLM 配置")


class TCMAgentState(TCMInputState):
    """中医智能体主状态"""
    model_config = {"extra": "allow"}

    router: Optional[TCMRouter] = Field(default=None, description="路由结果")
    syndrome_result: Optional[SyndromeResult] = Field(default=None, description="辨证结果")
    steps: Annotated[list[str], reduce_list] = Field(default_factory=list, description="执行步骤")
    answer: Annotated[str, reduce_str] = Field(default="", description="最终回答")
    error: Optional[str] = Field(default=None, description="错误信息")

    # 支持字典式访问（兼容 LangGraph）
    def __getitem__(self, key: str):
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"'{key}' not found in {self.__class__.__name__}")

    def __setitem__(self, key: str, value):
        setattr(self, key, value)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class TCMOutputState(BaseModel):
    """中医智能体输出状态"""
    answer: str = Field(description="最终回答")
    query_type: TCMQueryType = Field(description="查询类型")
    syndrome_result: Optional[SyndromeResult] = Field(default=None, description="辨证结果")
    steps: list[str] = Field(default_factory=list, description="执行步骤")
