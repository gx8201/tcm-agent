"""
TCM Supervisor 多Agent协调器（精简版）

基于 Supervisor 模式的多Agent架构：
User Query → TCMSupervisor → [Specialist Agents] → Response
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("tcm_supervisor")


class AgentRole(str, Enum):
    """Agent 角色"""
    SUPERVISOR = "supervisor"
    DIAGNOSIS = "diagnosis"
    PRESCRIPTION = "prescription"
    WELLNESS = "wellness"
    HERB = "herb"
    GENERAL = "general"


class ResponseType(str, Enum):
    """响应类型"""
    SYNTHESIZED = "synthesized"
    DIRECT_PASS = "direct_pass"
    HANDOFF = "handoff"
    ERROR = "error"


@dataclass
class AgentTask:
    """Agent 任务"""
    task_id: str
    role: AgentRole
    description: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Agent 响应"""
    agent_role: AgentRole
    task_id: str
    response_type: ResponseType
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    handoff_target: Optional[AgentRole] = None


class TCMSupervisor:
    """TCM 多Agent协调器"""

    def __init__(self, specialists: Optional[Dict[AgentRole, Callable]] = None):
        self.specialists = specialists or {}

    def register_specialist(self, role: AgentRole, executor: Callable):
        """注册专门Agent"""
        self.specialists[role] = executor
        logger.info(f"注册专门Agent: {role}")

    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """处理用户查询"""
        logger.info(f"处理查询: {query[:50]}...")

        # 分解查询
        tasks = self._decompose_query(query, context)

        if not tasks:
            return await self._handle_with_general(query, context)

        # 单任务 Direct Pass
        if len(tasks) == 1:
            response = await self._execute_agent(tasks[0], context)
            if response.response_type == ResponseType.DIRECT_PASS:
                return {
                    "type": "direct_pass",
                    "agent": response.agent_role,
                    "content": response.content,
                }

        # 多任务并行执行
        import asyncio
        responses = await asyncio.gather(
            *[self._execute_agent(t, context) for t in tasks],
            return_exceptions=True
        )
        valid_responses = [r for r in responses if isinstance(r, AgentResponse)]

        # 合成结果
        if not valid_responses:
            return {"type": "error", "content": "无法处理此查询"}

        if len(valid_responses) == 1:
            return {
                "type": "direct_pass",
                "agent": valid_responses[0].agent_role,
                "content": valid_responses[0].content,
            }

        # 多响应合成
        parts = [f"【{r.agent_role}】\n{r.content}" for r in valid_responses if r.content]
        return {
            "type": "synthesized",
            "content": "\n\n".join(parts),
        }

    def _decompose_query(self, query: str, context: Optional[Dict[str, Any]]) -> List[AgentTask]:
        """分解查询为子任务"""
        tasks = []
        query_lower = query.lower()
        now = datetime.now().timestamp()

        if any(kw in query_lower for kw in ["诊断", "辨证", "症状", "病因"]):
            tasks.append(AgentTask(
                task_id=f"diagnosis_{now}", role=AgentRole.DIAGNOSIS,
                description="分析症状并进行中医辨证",
                input_data={"query": query}
            ))

        if any(kw in query_lower for kw in ["方剂", "处方", "药方"]):
            tasks.append(AgentTask(
                task_id=f"prescription_{now}", role=AgentRole.PRESCRIPTION,
                description="推荐合适的方剂",
                input_data={"query": query}
            ))

        if any(kw in query_lower for kw in ["养生", "保健", "调理"]):
            tasks.append(AgentTask(
                task_id=f"wellness_{now}", role=AgentRole.WELLNESS,
                description="提供养生建议",
                input_data={"query": query}
            ))

        if any(kw in query_lower for kw in ["药材", "中药", "草药"]):
            tasks.append(AgentTask(
                task_id=f"herb_{now}", role=AgentRole.HERB,
                description="解答药材相关问题",
                input_data={"query": query}
            ))

        return tasks

    async def _execute_agent(self, task: AgentTask, context: Optional[Dict[str, Any]]) -> AgentResponse:
        """执行单个Agent"""
        specialist = self.specialists.get(task.role)
        if specialist is None:
            return AgentResponse(
                agent_role=task.role, task_id=task.task_id,
                response_type=ResponseType.ERROR,
                content=f"Agent {task.role} 未注册", confidence=0.0
            )

        try:
            response = await specialist(task, context or {})
            if not isinstance(response, AgentResponse):
                response = AgentResponse(
                    agent_role=task.role, task_id=task.task_id,
                    response_type=ResponseType.SYNTHESIZED,
                    content=str(response), confidence=0.5
                )
            return response
        except Exception as e:
            logger.error(f"Agent {task.role} 执行异常: {e}")
            return AgentResponse(
                agent_role=task.role, task_id=task.task_id,
                response_type=ResponseType.ERROR,
                content=f"执行失败: {str(e)}", confidence=0.0
            )

    async def _handle_with_general(self, query: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """由通用Agent处理"""
        specialist = self.specialists.get(AgentRole.GENERAL)
        if not specialist:
            return {"type": "error", "content": "通用Agent未注册"}

        task = AgentTask(
            task_id=f"general_{datetime.now().timestamp()}",
            role=AgentRole.GENERAL,
            description="通用中医咨询",
            input_data={"query": query}
        )

        response = await specialist(task, context or {})
        return {"type": "general", "content": response.content}


def create_supervisor() -> TCMSupervisor:
    """创建 Supervisor 实例"""
    return TCMSupervisor()
