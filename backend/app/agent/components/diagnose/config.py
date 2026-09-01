"""
诊断子图配置参数
"""


class DiagnoseConfig:
    """诊断子图配置"""

    # 追问控制
    MAX_FOLLOW_UP_ROUNDS: int = 4
    MIN_REQUIRED_CATEGORIES: int = 4

    # 复杂度阈值
    SIMPLE_THRESHOLD: int = 3      # ≤3分：简单
    MODERATE_THRESHOLD: int = 6    # ≤6分：中等，>6分：复杂

    # 多模态
    ENABLE_TONGUE_REQUEST: bool = True

    # LLM 参数
    COLLECTION_TEMPERATURE: float = 0.7
    DIAGNOSIS_TEMPERATURE: float = 0.3

    # 错误响应
    ERROR_RESPONSES = {
        "collection_failed": "抱歉，我没有完全理解您的描述。能否再详细说明一下您的症状？",
        "diagnosis_failed": "抱歉，根据目前的信息，我无法给出确切的判断。建议您前往医院进行详细检查。",
    }


# 全局配置实例
diagnose_config = DiagnoseConfig()
