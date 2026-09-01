"""
专门Agent实现（精简版）

展示各个专门Agent的实现
"""

import logging
from typing import Dict, Any

from .tcm_supervisor import AgentRole, AgentTask, AgentResponse, ResponseType

logger = logging.getLogger("specialists")


class BaseSpecialist:
    """专门Agent基类"""

    def __init__(self, role: AgentRole):
        self.role = role

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        raise NotImplementedError

    def _create_response(self, task: AgentTask, content: str,
                         response_type: ResponseType = ResponseType.SYNTHESIZED,
                         confidence: float = 0.8, **metadata) -> AgentResponse:
        return AgentResponse(
            agent_role=self.role, task_id=task.task_id,
            response_type=response_type, content=content,
            confidence=confidence, data=metadata
        )


class DiagnosisSpecialist(BaseSpecialist):
    """诊断专门Agent"""

    def __init__(self):
        super().__init__(AgentRole.DIAGNOSIS)

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        """执行诊断任务"""
        from app.agent.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        query = task.input_data.get("query", "")

        llm = get_llm(temperature=0.3)
        prompt = """你是一位经验丰富的中医师。请根据患者的描述进行辨证分析。
输出格式：证型名称、辨证依据、治则治法、调理建议。
注意：仅供参考，建议就医确认。"""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])

        return self._create_response(task, response.content, ResponseType.DIRECT_PASS)


class PrescriptionSpecialist(BaseSpecialist):
    """方剂专门Agent"""

    def __init__(self):
        super().__init__(AgentRole.PRESCRIPTION)

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        from app.agent.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        query = task.input_data.get("query", "")
        llm = get_llm(temperature=0.3)
        prompt = """你是一位精通方剂学的中医专家。请根据用户问题介绍方剂信息。
包括：方剂名称、出处、组成、功效、主治、注意事项。
注意：方剂推荐仅供参考，具体用药请咨询专业中医师。"""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])

        return self._create_response(task, response.content, ResponseType.DIRECT_PASS)


class WellnessSpecialist(BaseSpecialist):
    """养生专门Agent"""

    def __init__(self):
        super().__init__(AgentRole.WELLNESS)

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        from app.agent.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        query = task.input_data.get("query", "")
        llm = get_llm(temperature=0.7)
        prompt = """你是一位擅长中医养生的专家。请为用户提供个性化的养生建议。
包括：饮食调理、起居调摄、情志调养、运动锻炼等方面。"""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])

        return self._create_response(task, response.content, ResponseType.DIRECT_PASS)


class HerbSpecialist(BaseSpecialist):
    """药材专门Agent"""

    def __init__(self):
        super().__init__(AgentRole.HERB)

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        from app.agent.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        query = task.input_data.get("query", "")
        llm = get_llm(temperature=0.3)
        prompt = """你是一位精通中药学的专家。请解答药材相关问题。
包括：性味归经、功效主治、用法用量、配伍禁忌等。
注意：涉及配伍禁忌时必须明确提醒。"""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])

        return self._create_response(task, response.content, ResponseType.DIRECT_PASS)


class GeneralSpecialist(BaseSpecialist):
    """通用咨询Agent"""

    def __init__(self):
        super().__init__(AgentRole.GENERAL)

    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> AgentResponse:
        from app.agent.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        query = task.input_data.get("query", "")
        llm = get_llm(temperature=0.7)
        prompt = """你是中医咨询助手，可以解答关于中医诊断、方剂、养生、药材等方面的问题。
请用通俗易懂的语言回答。"""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])

        return self._create_response(task, response.content, ResponseType.DIRECT_PASS)


def get_all_specialists() -> Dict[AgentRole, callable]:
    """获取所有专门Agent的执行器"""
    diagnosis = DiagnosisSpecialist()
    prescription = PrescriptionSpecialist()
    wellness = WellnessSpecialist()
    herb = HerbSpecialist()
    general = GeneralSpecialist()

    return {
        AgentRole.DIAGNOSIS: diagnosis.execute,
        AgentRole.PRESCRIPTION: prescription.execute,
        AgentRole.WELLNESS: wellness.execute,
        AgentRole.HERB: herb.execute,
        AgentRole.GENERAL: general.execute,
    }
