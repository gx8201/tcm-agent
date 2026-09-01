"""
诊断流处理器

处理中医问诊相关的查询
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent.tcm_states import TCMAgentState
from .builder import get_diagnose_graph
from app.agent.llm import get_llm
from app.agent.neo4j_service import query_treatment_chain

logger = logging.getLogger("diagnose_handler")


async def handle_diagnose_query(state: TCMAgentState, config: RunnableConfig = None) -> dict:
    """
    处理诊断类查询

    通过调用诊断子图实现：
    - 多轮信息收集
    - 复杂度评估
    - 分级辨证（简单/中等）
    """
    messages = state.messages
    if not messages:
        return {"error": "No messages to process"}

    # 获取最后一条用户消息
    last_user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_query = msg.content
            break

    if not last_user_query:
        return {"error": "No user query found"}

    try:
        # 获取诊断子图
        diagnose_graph = get_diagnose_graph()

        # 准备子图输入
        subgraph_input = {
            "query": last_user_query,
            "messages": list(messages),
            "user_profile": state.user_profile or {},
            "llm_config": state.llm_config,
        }

        # 调用诊断子图
        logger.info("调用诊断子图...")
        result = await diagnose_graph.ainvoke(subgraph_input, config or {})

        # 提取结果
        answer = result.get("answer", "")
        diagnosis_result = result.get("diagnosis_result")
        steps = result.get("steps", [])
        follow_up_question = result.get("follow_up_question")

        # 如果有追问问题，使用追问问题作为回复
        if follow_up_question and not answer:
            answer = follow_up_question

        # 从诊断结果中提取症状关键词，查询知识图谱
        kg_context = ""
        try:
            # 用原始查询提取关键词（前4字作为症状搜索）
            query_keywords = []
            # 常见症状关键词映射
            symptom_keywords = {
                "胃": "胃", "痛": "痛", "咳": "咳", "失眠": "不眠",
                "乏力": "乏力", "头痛": "头痛", "发烧": "发热",
                "恶心": "呕", "腹泻": "泄泻", "便秘": "便秘",
                "腰": "腰", "膝盖": "膝", "心悸": "心悸",
                "头晕": "眩晕", "失眠多梦": "不眠",
                "睡不着": "不眠", "难以入睡": "不眠",
            }
            for key, symptom in symptom_keywords.items():
                if key in last_user_query:
                    query_keywords.append(symptom)

            # 如果没有匹配到，用查询的前4字
            if not query_keywords and len(last_user_query) >= 2:
                query_keywords.append(last_user_query[:4])

            if query_keywords:
                kg_result = query_treatment_chain(query_keywords)
                herbs = kg_result.get("herbs", [])
                formulas = kg_result.get("formulas", [])

                if herbs or formulas:
                    kg_context = "\n\n---\n### 📚 知识图谱参考\n"
                    if formulas:
                        kg_context += "\n**相关方剂：**\n"
                        for f in formulas[:5]:
                            herb_names = ", ".join([h["name"] for h in f["herbs"][:8]])
                            kg_context += f"- **{f['name']}**：{herb_names}\n"
                    if herbs:
                        kg_context += "\n**相关药材：**\n"
                        for h in herbs[:5]:
                            smell = h.get('smell', '') or ''
                            cure = h.get('cure', '') or ''
                            symptoms = h.get('symptoms', [])
                            symptom_str = '、'.join(symptoms[:3]) if symptoms else ''
                            
                            # 构建描述
                            desc_parts = []
                            if smell:
                                desc_parts.append(f"性味：{smell}")
                            if cure:
                                desc_parts.append(f"功效：{cure[:50]}")
                            if symptom_str:
                                desc_parts.append(f"主治：{symptom_str}")
                            
                            desc = '；'.join(desc_parts) if desc_parts else '详见知识图谱'
                            kg_context += f"- **{h['name']}**：{desc}\n"
                    kg_context += "\n> ⚠️ 以上方剂仅供参考，需由中医师辨证后使用。\n"

        except Exception as e:
            logger.warning(f"知识图谱查询失败（不影响主流程）: {e}")

        # 追加知识图谱上下文到回答
        if kg_context and answer:
            answer += kg_context

        logger.info(f"诊断子图完成，步骤: {steps}")

        return {
            "answer": answer,
            "steps": steps or ["诊断处理: 完成中医问诊分析"],
        }

    except Exception as e:
        logger.error(f"诊断处理失败: {e}", exc_info=True)
        return await _fallback_diagnose(last_user_query, str(e))


async def _fallback_diagnose(query: str, error: str) -> dict:
    """降级处理：当子图调用失败时使用简单 LLM 处理"""
    logger.warning(f"诊断子图失败，降级到简单处理: {error}")

    FALLBACK_PROMPT = """你是一位经验丰富的中医师，擅长望闻问切四诊合参。

## 问诊原则
1. 详细了解患者的症状、病史、生活习惯
2. 注意症状的性质、部位、时间规律
3. 结合四诊信息进行辨证分析
4. 给出中医辨证和调理建议

## 注意事项
- 始终提醒患者：中医建议仅供参考，严重情况请及时就医
- 不做西医诊断，不开具处方药
"""

    try:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=FALLBACK_PROMPT),
            HumanMessage(content=query)
        ])
        return {
            "answer": response.content,
            "steps": [f"诊断处理: 降级处理完成 (原因: {error})"],
        }
    except Exception as e2:
        logger.error(f"降级处理也失败: {e2}", exc_info=True)
        return {
            "answer": "抱歉，问诊分析过程中出现问题。请稍后重试，或换种方式描述您的症状。",
            "error": str(e2),
            "steps": [f"诊断处理: 失败 - {str(e2)}"],
        }
