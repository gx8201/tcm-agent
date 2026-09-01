"""
医案积累模块

功能：
- 从成功的问诊对话中提取医案信息
- 保存医案到知识图谱（Neo4j）
- 查询相似医案
"""

import os
import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from datetime import datetime

logger = logging.getLogger("case_accumulation")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
if not NEO4J_PASSWORD:
    logger.warning("NEO4J_PASSWORD 未设置，医案积累功能将不可用")


def save_case(
    case_id: str,
    symptoms: List[str],
    diagnosis: str,
    treatment: str,
    herbs: List[str],
    formulas: List[str],
    conversation_id: str,
    user_id: str = "anonymous"
) -> bool:
    """
    保存医案到知识图谱
    
    Args:
        case_id: 医案ID
        symptoms: 症状列表
        diagnosis: 辨证结论
        treatment: 调理建议
        herbs: 相关药材
        formulas: 相关方剂
        conversation_id: 对话ID
        user_id: 用户ID
    
    Returns:
        是否保存成功
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=30)
        
        with driver.session() as s:
            # 创建医案节点
            s.run(
                """
                MERGE (c:MedicalCase {id: $case_id})
                SET c.symptoms = $symptoms,
                    c.diagnosis = $diagnosis,
                    c.treatment = $treatment,
                    c.conversation_id = $conversation_id,
                    c.user_id = $user_id,
                    c.created_at = $created_at
                """,
                case_id=case_id,
                symptoms=symptoms,
                diagnosis=diagnosis,
                treatment=treatment,
                conversation_id=conversation_id,
                user_id=user_id,
                created_at=datetime.now().isoformat()
            )
            
            # 建立症状关系
            for symptom in symptoms:
                s.run(
                    """
                    MATCH (c:MedicalCase {id: $case_id})
                    MERGE (sy:Symptom {name: $symptom})
                    MERGE (c)-[:HAS_SYMPTOM]->(sy)
                    """,
                    case_id=case_id,
                    symptom=symptom
                )
            
            # 建立方剂关系
            for formula in formulas:
                s.run(
                    """
                    MATCH (c:MedicalCase {id: $case_id})
                    MERGE (f:Formula {name: $formula})
                    MERGE (c)-[:USED_FORMULA]->(f)
                    """,
                    case_id=case_id,
                    formula=formula
                )
            
            # 建立药材关系
            for herb in herbs:
                s.run(
                    """
                    MATCH (c:MedicalCase {id: $case_id})
                    MERGE (h:Herb {name: $herb})
                    MERGE (c)-[:USED_HERB]->(h)
                    """,
                    case_id=case_id,
                    herb=herb
                )
        
        driver.close()
        logger.info(f"医案已保存: {case_id}")
        return True
        
    except Exception as e:
        logger.error(f"保存医案失败: {e}", exc_info=True)
        return False


def find_similar_cases(symptoms: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """
    查找相似医案
    
    Args:
        symptoms: 症状列表
        limit: 返回数量限制
    
    Returns:
        相似医案列表
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=30)
        
        with driver.session() as s:
            result = s.run(
                """
                MATCH (c:MedicalCase)-[:HAS_SYMPTOM]->(sy:Symptom)
                WHERE sy.name IN $symptoms
                WITH c, count(sy) AS match_count
                ORDER BY match_count DESC
                LIMIT $limit
                MATCH (c)-[:HAS_SYMPTOM]->(sy:Symptom)
                MATCH (c)-[:USED_FORMULA]->(f:Formula)
                RETURN c.id AS case_id,
                       c.symptoms AS symptoms,
                       c.diagnosis AS diagnosis,
                       c.treatment AS treatment,
                       collect(DISTINCT sy.name) AS matched_symptoms,
                       collect(DISTINCT f.name) AS formulas,
                       match_count
                """,
                symptoms=symptoms,
                limit=limit
            )
            
            cases = []
            for rec in result:
                cases.append({
                    "case_id": rec["case_id"],
                    "symptoms": rec["symptoms"],
                    "diagnosis": rec["diagnosis"],
                    "treatment": rec["treatment"],
                    "matched_symptoms": rec["matched_symptoms"],
                    "formulas": rec["formulas"],
                    "match_count": rec["match_count"]
                })
            
            driver.close()
            return cases
            
    except Exception as e:
        logger.error(f"查找相似医案失败: {e}", exc_info=True)
        return []


def extract_case_from_conversation(conversation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    从对话记录中提取医案信息
    
    Args:
        conversation: 对话记录
    
    Returns:
        提取的医案信息或None
    """
    try:
        messages = conversation.get("messages", [])
        if not messages:
            return None
        
        # 找到最后一条诊断相关的消息
        diagnosis_msg = None
        for msg in reversed(messages):
            if msg.get("intent") == "diagnosis":
                diagnosis_msg = msg
                break
        
        if not diagnosis_msg:
            return None
        
        user_message = diagnosis_msg.get("user_message", "")
        bot_response = diagnosis_msg.get("bot_response", "")
        
        # 简单提取症状（从用户消息中）
        symptoms = []
        symptom_keywords = ["失眠", "胃痛", "咳嗽", "头痛", "乏力", "发热", "恶心", "腹泻"]
        for keyword in symptom_keywords:
            if keyword in user_message:
                symptoms.append(keyword)
        
        # 提取方剂（从知识图谱参考部分）
        formulas = []
        if "相关方剂" in bot_response:
            import re
            formula_matches = re.findall(r'\*\*(.*?)\*\*：', bot_response)
            formulas = [f for f in formula_matches if f and len(f) < 10]
        
        # 提取诊断结论
        diagnosis = ""
        if "辨证结论" in bot_response:
            import re
            match = re.search(r'辨证结论[：:]\s*(.*?)(?:\n|$)', bot_response)
            if match:
                diagnosis = match.group(1).strip()
        
        if not symptoms:
            return None
        
        return {
            "case_id": f"case_{conversation.get('conversation_id', 'unknown')}",
            "symptoms": symptoms,
            "diagnosis": diagnosis or "待完善",
            "treatment": bot_response[:500] if bot_response else "",
            "herbs": [],
            "formulas": formulas,
            "conversation_id": conversation.get("conversation_id", ""),
            "user_id": conversation.get("user_id", "anonymous")
        }
        
    except Exception as e:
        logger.error(f"提取医案信息失败: {e}", exc_info=True)
        return None


def get_case_stats() -> Dict[str, Any]:
    """
    获取医案统计信息
    
    Returns:
        统计信息
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=30)
        
        with driver.session() as s:
            result = s.run("MATCH (c:MedicalCase) RETURN count(c) AS total")
            total = result.single()["total"]
            
            result = s.run(
                """
                MATCH (c:MedicalCase)-[:HAS_SYMPTOM]->(sy:Symptom)
                RETURN sy.name AS symptom, count(c) AS count
                ORDER BY count DESC
                LIMIT 10
                """)
            
            top_symptoms = []
            for rec in result:
                top_symptoms.append({"symptom": rec["symptom"], "count": rec["count"]})
        
        driver.close()
        
        return {
            "total_cases": total,
            "top_symptoms": top_symptoms
        }
        
    except Exception as e:
        logger.error(f"获取医案统计失败: {e}", exc_info=True)
        return {"total_cases": 0, "top_symptoms": []}
