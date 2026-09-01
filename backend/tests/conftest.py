"""
pytest 全局 fixtures

提供：
- 设置 USE_MOCK_LLM=true 环境变量
- 创建 httpx.AsyncClient 测试客户端
- 重置各模块单例
"""

import os
import sys
import pytest
import pytest_asyncio
import httpx

# 确保 backend/ 目录在 Python 路径中
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture(autouse=True, scope="session")
def _setup_mock_env():
    """在整个测试会话中启用 Mock LLM 模式"""
    os.environ["USE_MOCK_LLM"] = "true"
    os.environ["DEEPSEEK_API_KEY"] = "sk-test-mock-key-for-testing"
    os.environ["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"
    yield
    os.environ.pop("USE_MOCK_LLM", None)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DEEPSEEK_BASE_URL", None)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前重置所有模块级单例，确保测试隔离"""
    # 重置意图分类器单例
    import app.agent.intent_recognition.intent_classifier as ic_mod
    ic_mod._classifier = None

    # 重置意图路由器单例
    import app.agent.intent_recognition.router.intent_router as ir_mod
    ir_mod._router = None

    # 重置规则路由器单例
    import app.agent.intent_recognition.router.rule_router as rr_mod
    rr_mod._router_instance = None

    # 重置诊断子图单例
    import app.agent.components.diagnose.builder as db_mod
    db_mod._diagnose_graph = None

    yield


@pytest_asyncio.fixture
async def client():
    """创建异步 HTTP 测试客户端"""
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
