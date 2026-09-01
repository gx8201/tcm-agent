"""
诊断子图状态定义
"""

from typing import List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict, NotRequired
from operator import add
from langchain_core.messages import BaseMessage

from app.agent.tcm_states import LLMConfig


class DiagnoseInputState(TypedDict):
    """诊断子图输入状态"""
    query: str
    messages: List[BaseMessage]
    user_profile: Dict[str, Any]
    llm_config: Optional[LLMConfig]
    extracted_entities: NotRequired[Dict[str, Any]]


class DiagnoseOverallState(TypedDict):
    """诊断子图内部状态"""
    # 输入继承
    query: str
    messages: List[BaseMessage]
    user_profile: Dict[str, Any]
    llm_config: Optional[LLMConfig]
    extracted_entities: NotRequired[Dict[str, Any]]

    # 信息收集
    collected_info: NotRequired[Dict[str, Any]]
    collection_history: NotRequired[Annotated[List[Dict[str, Any]], add]]
    follow_up_count: NotRequired[int]

    # 多模态
    tongue_analysis: NotRequired[Dict[str, Any]]
    report_analysis: NotRequired[Dict[str, Any]]

    # 复杂度评估
    complexity: NotRequired[Dict[str, Any]]

    # 辨证结果
    diagnosis_result: NotRequired[Dict[str, Any]]

    # 流程控制
    next_action: NotRequired[str]
    steps: NotRequired[Annotated[List[str], add]]

    # 输出字段
    answer: NotRequired[str]
    follow_up_question: NotRequired[str]


class DiagnoseOutputState(TypedDict):
    """诊断子图输出状态"""
    answer: str
    diagnosis_result: NotRequired[Dict[str, Any]]
    steps: List[str]
    follow_up_question: NotRequired[str]
