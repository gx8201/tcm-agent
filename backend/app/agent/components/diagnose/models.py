"""
诊断子图数据模型

定义诊断过程中使用的核心数据结构
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    """复杂度级别"""
    SIMPLE = "simple"       # 简单：LLM 直接辨证
    MODERATE = "moderate"   # 中等：RAG 辅助
    COMPLEX = "complex"     # 复杂：深度搜索


class CollectedDiagnoseInfo(BaseModel):
    """
    已收集的诊断信息 - 基于中医十问

    中医十问歌：
    一问寒热二问汗，三问头身四问便，
    五问饮食六问胸，七聋八渴俱当辨，
    九问旧病十问因，再兼服药参机变。
    """

    # 主诉
    chief_complaint: Optional[str] = None
    onset_time: Optional[str] = None
    duration: Optional[str] = None

    # 十问信息
    cold_heat: Optional[str] = None       # 寒热
    sweat: Optional[str] = None           # 汗出
    head_body: Optional[str] = None       # 头身
    urine_stool: Optional[str] = None     # 二便
    diet: Optional[str] = None            # 饮食
    chest_abdomen: Optional[str] = None   # 胸腹
    sleep: Optional[str] = None           # 睡眠
    emotion: Optional[str] = None         # 情志

    # 望诊
    tongue: Optional[Dict[str, str]] = None  # 舌象
    complexion: Optional[str] = None         # 面色

    # 既往史
    medical_history: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    allergies: Optional[List[str]] = None

    # 其他
    other_symptoms: Optional[List[str]] = None

    def get_missing_categories(self) -> List[str]:
        """获取缺失的必要信息类别"""
        required = {
            "cold_heat": "寒热",
            "sweat": "汗出",
            "head_body": "头身",
            "urine_stool": "二便",
            "diet": "饮食",
            "sleep": "睡眠",
        }
        missing = []
        for field, name in required.items():
            if getattr(self, field) is None:
                missing.append(name)
        return missing

    def is_sufficient(self, min_categories: int = 4) -> bool:
        """判断信息是否足够"""
        missing = self.get_missing_categories()
        return len(missing) <= (6 - min_categories)

    def get_filled_count(self) -> int:
        """获取已填充的信息类别数量"""
        fields = [
            "chief_complaint", "cold_heat", "sweat", "head_body",
            "urine_stool", "diet", "chest_abdomen", "sleep", "emotion"
        ]
        return sum(1 for f in fields if getattr(self, f) is not None)

    def get_all_symptoms(self) -> List[str]:
        """获取所有已收集的症状"""
        symptoms = []
        for field in ["chief_complaint", "cold_heat", "sweat", "head_body",
                       "urine_stool", "diet", "chest_abdomen", "sleep", "emotion"]:
            val = getattr(self, field)
            if val:
                symptoms.append(val)
        if self.other_symptoms:
            symptoms.extend(self.other_symptoms)
        return symptoms

    def to_summary(self) -> str:
        """生成信息摘要"""
        parts = []
        field_names = {
            "chief_complaint": "主诉", "duration": "病程",
            "cold_heat": "寒热", "sweat": "汗出",
            "head_body": "头身", "urine_stool": "二便",
            "diet": "饮食", "chest_abdomen": "胸腹",
            "sleep": "睡眠", "emotion": "情志",
            "complexion": "面色",
        }
        for field, name in field_names.items():
            val = getattr(self, field)
            if val:
                parts.append(f"{name}：{val}")
        if self.tongue:
            tongue_str = "、".join(f"{k}:{v}" for k, v in self.tongue.items())
            parts.append(f"舌象：{tongue_str}")
        if self.medical_history:
            parts.append(f"既往史：{', '.join(self.medical_history)}")
        return "\n".join(parts) if parts else "暂无收集到的信息"


class ComplexityAssessment(BaseModel):
    """复杂度评估结果"""
    level: ComplexityLevel
    score: int = Field(ge=0, le=10)
    factors: Dict[str, int] = Field(default_factory=dict)
    reasoning: str = ""


class DiagnosisResult(BaseModel):
    """辨证结果"""
    ba_gang: Dict[str, str] = Field(default_factory=dict)  # 八纲辨证
    syndrome: str = ""                                      # 主要证型
    syndrome_secondary: Optional[List[str]] = None          # 兼证
    etiology: Optional[str] = None                          # 病因
    pathogenesis: Optional[str] = None                      # 病机
    treatment_principle: Optional[str] = None               # 治则
    treatment_method: Optional[str] = None                  # 治法
    recommendations: Optional[List[str]] = None             # 调理建议
    warnings: Optional[List[str]] = None                    # 注意事项
    should_seek_doctor: bool = False                        # 是否建议就医
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_display(self) -> str:
        """生成显示文本"""
        parts = [f"**证型**：{self.syndrome}"]
        if self.syndrome_secondary:
            parts.append(f"**兼证**：{', '.join(self.syndrome_secondary)}")
        if self.ba_gang:
            parts.append(f"**八纲**：{'、'.join(f'{k}:{v}' for k, v in self.ba_gang.items())}")
        if self.etiology:
            parts.append(f"**病因**：{self.etiology}")
        if self.pathogenesis:
            parts.append(f"**病机**：{self.pathogenesis}")
        if self.treatment_principle:
            parts.append(f"**治则**：{self.treatment_principle}")
        if self.treatment_method:
            parts.append(f"**治法**：{self.treatment_method}")
        if self.recommendations:
            parts.append("**调理建议**：")
            for i, rec in enumerate(self.recommendations, 1):
                parts.append(f"  {i}. {rec}")
        if self.warnings:
            parts.append("**注意事项**：")
            for w in self.warnings:
                parts.append(f"  - {w}")
        return "\n".join(parts)
