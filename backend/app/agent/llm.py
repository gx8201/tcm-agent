"""
LLM 提供者 - 使用 langchain-deepseek

精简版：直接使用 ChatDeepSeek，去除多 provider 复杂逻辑
支持 USE_MOCK_LLM=true 环境变量启用 Mock 模式
"""

import os
import json
import logging
from enum import Enum as _PyEnum
from typing import Any, Dict, List, Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ============================================================
# Mock LLM 基础设施（供测试使用）
# ============================================================

class _StructuredOutputWrapper:
    """
    包装 MockChatModel 以支持 with_structured_output(schema) 调用。
    每次调用 consume 下一个 mock 响应并尝试解析为指定 schema 的实例。
    """

    def __init__(self, mock_model: "MockChatModel", schema: Type[BaseModel]):
        self._mock = mock_model
        self._schema = schema

    def _parse(self, text: str) -> Any:
        """将文本解析为 schema 实例"""
        try:
            data = json.loads(text)
            return self._schema.model_validate(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.debug("Mock 响应非合法 JSON，使用 schema 默认值")
        except Exception as e:
            logger.debug(f"Mock 响应解析异常: {e}，使用 schema 默认值")

        # 尝试无参构造
        try:
            return self._schema()
        except Exception:
            pass

        # 手动构造默认值
        fields = {}
        for name, field_info in self._schema.model_fields.items():
            default = field_info.default
            if default is not None and default is not ...:
                fields[name] = default
                continue

            annotation = field_info.annotation
            if annotation is None:
                fields[name] = None
            elif isinstance(annotation, type) and issubclass(annotation, _PyEnum):
                # Enum 类型：取第一个枚举值
                fields[name] = list(annotation)[0]
            elif annotation is str:
                fields[name] = ""
            elif annotation is float:
                fields[name] = 0.0
            elif annotation is int:
                fields[name] = 0
            elif annotation is bool:
                fields[name] = False
            elif annotation is list:
                fields[name] = []
            elif annotation is dict:
                fields[name] = {}
            elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                fields[name] = annotation()
            else:
                # Optional[X] 等复杂类型
                fields[name] = None

        return self._schema(**fields)

    async def ainvoke(self, messages: Any, **kwargs) -> Any:
        text = self._mock._next_response()
        return self._parse(text)

    def invoke(self, messages: Any, **kwargs) -> Any:
        text = self._mock._next_response()
        return self._parse(text)

    async def agenerate(self, messages: List[List[BaseMessage]], **kwargs) -> ChatResult:
        text = self._mock._next_response()
        parsed = self._parse(text)
        message = AIMessage(content=json.dumps(parsed.model_dump(), ensure_ascii=False))
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools, **kwargs):
        return self


class MockChatModel(BaseChatModel):
    """
    测试用 Mock LLM，支持：
    - 按队列顺序返回预设响应
    - with_structured_output(schema) 返回可解析 JSON 的 wrapper
    - 支持异步调用 (ainvoke / agenerate)
    - 环境变量 USE_MOCK_RESPONSES 可注入 JSON 数组作为响应列表
    """
    responses: List[str] = []
    model_name: str = "mock-model"

    # 用于追踪调用顺序的内部计数器
    _call_index: int = 0

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        self._call_index = 0
        # 支持通过环境变量注入 mock 响应
        env_responses = os.getenv("USE_MOCK_RESPONSES")
        if env_responses and not self.responses:
            try:
                self.responses = json.loads(env_responses)
            except json.JSONDecodeError:
                pass

    @property
    def _llm_type(self) -> str:
        return "mock-chat-model"

    def _next_response(self) -> str:
        """按顺序获取下一个 mock 响应；如果队列用完则重复最后一个"""
        if not self.responses:
            return "mock response"
        if self._call_index < len(self.responses):
            resp = self.responses[self._call_index]
            self._call_index += 1
            return resp
        # 队列耗尽：抛出异常，防止测试数据不足时静默通过
        raise IndexError(
            f"MockChatModel 响应队列已耗尽（共 {len(self.responses)} 条，已调用 {self._call_index + 1} 次）。"
            f"请在 mock_responses 中补充更多响应，或检查测试调用链是否超出预期。"
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self._next_response()
        message = AIMessage(content=text)
        return ChatResult(
            generations=[ChatGeneration(message=message)],
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    def with_structured_output(self, schema: Type[BaseModel], **kwargs) -> Any:
        """返回支持结构化输出的包装器"""
        return _StructuredOutputWrapper(self, schema)

    def bind_tools(self, tools, **kwargs):
        """支持 bind_tools 调用（LangChain 内部 with_structured_output 可能调用此方法）"""
        return self


# ============================================================
# 公共接口
# ============================================================

def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    responses: Optional[List[str]] = None,
) -> BaseChatModel:
    """
    获取 LLM 实例（使用 DeepSeek）

    当 USE_MOCK_LLM=true 时返回 MockChatModel（测试模式）。

    Args:
        model: 模型名称，默认从环境变量读取
        temperature: 温度参数
        max_tokens: 最大 token 数
        responses: Mock 模式下的预设响应列表（仅在 USE_MOCK_LLM=true 时生效）

    Returns:
        BaseChatModel: LLM 实例
    """
    # Mock 模式
    if os.getenv("USE_MOCK_LLM", "").lower() == "true":
        return MockChatModel(
            responses=responses or ["mock response"],
            model_name="mock-deepseek",
        )

    # 真实模式
    from langchain_deepseek import ChatDeepSeek

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    model_name = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY 未设置。请在 .env 文件中配置 DEEPSEEK_API_KEY。"
        )

    return ChatDeepSeek(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
