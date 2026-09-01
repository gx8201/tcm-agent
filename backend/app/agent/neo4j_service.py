"""
Neo4j 服务 - 中医知识图谱查询接口

连接本地 Neo4j 数据库，提供药材-方剂-症状查询
"""

import os
import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

logger = logging.getLogger("neo4j_service")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
if not NEO4J_PASSWORD:
    logger.warning("NEO4J_PASSWORD 未设置，Neo4j 功能将不可用")

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        if not NEO4J_PASSWORD:
            raise RuntimeError("NEO4J_PASSWORD 未配置，无法连接 Neo4j")
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            connection_timeout=30,
        )
    return _driver


def close():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def query_herb_for_symptom(symptom_keyword: str) -> List[Dict[str, Any]]:
    """根据症状关键词查询治疗药材"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (h:Herb)-[:TREATS]->(sy:Symptom)
            WHERE sy.name CONTAINS $keyword
            RETURN h.name AS herb, h.smell AS smell, h.cure AS cure,
                   collect(distinct sy.name) AS symptoms
            LIMIT 10
            """,
            keyword=symptom_keyword,
        )
        return [dict(rec) for rec in result]


def query_formula_for_symptom(symptom_keyword: str) -> List[Dict[str, Any]]:
    """根据症状关键词查询相关方剂"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (h:Herb)-[:TREATS]->(sy:Symptom)
            WHERE sy.name CONTAINS $keyword
            MATCH (p:Prescription)-[:CONTAINS]->(h)
            MATCH (f:Formula)-[:HAS_PRESCRIPTION]->(p)
            RETURN DISTINCT f.name AS formula, f.functions AS functions,
                   collect(distinct h.name) AS herbs
            LIMIT 10
            """,
            keyword=symptom_keyword,
        )
        return [dict(rec) for rec in result]


def query_herb_detail(herb_name: str) -> Optional[Dict[str, Any]]:
    """查询单味药材详情"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (h:Herb {name: $name})
            OPTIONAL MATCH (h)-[:TREATS]->(sy:Symptom)
            RETURN h.name AS name, h.alias AS alias, h.smell AS smell,
                   h.cure AS cure, collect(distinct sy.name) AS symptoms
            """,
            name=herb_name,
        )
        rec = result.single()
        return dict(rec) if rec else None


def query_formula_detail(formula_name: str) -> Optional[Dict[str, Any]]:
    """查询方剂详情（组成药材+剂量）"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (f:Formula {name: $name})-[:HAS_PRESCRIPTION]->(p:Prescription)
            MATCH (p)-[c:CONTAINS]->(h:Herb)
            RETURN f.name AS name, f.functions AS functions,
                   collect({herb: h.name, dose: c.dose}) AS composition
            LIMIT 5
            """,
            name=formula_name,
        )
        rec = result.single()
        return dict(rec) if rec else None


def query_treatment_chain(symptoms: List[str]) -> Dict[str, Any]:
    """
    完整治疗链查询：症状 → 药材 → 方剂

    这是问诊系统的核心查询，根据用户输入的症状列表，
    找出相关的治疗药材和推荐方剂。
    """
    driver = get_driver()
    herbs_map = {}  # herb_name -> {symptoms, ...}
    formulas_map = {}  # formula_name -> {herbs, functions}

    with driver.session() as s:
        for symptom in symptoms:
            # 路径1：直接查询治疗症状的药材（不依赖处方）
            result = s.run(
                """
                MATCH (h:Herb)-[:TREATS]->(sy:Symptom)
                WHERE sy.name CONTAINS $keyword
                RETURN h.name AS herb, h.smell AS smell, h.cure AS cure,
                       sy.name AS symptom, 'direct' AS source
                LIMIT 10
                """,
                keyword=symptom,
            )
            for rec in result:
                herb = rec["herb"]
                if herb not in herbs_map:
                    herbs_map[herb] = {
                        "name": herb,
                        "smell": rec["smell"],
                        "cure": rec["cure"],
                        "symptoms": [],
                        "source": "direct",
                    }
                if rec["symptom"] not in herbs_map[herb]["symptoms"]:
                    herbs_map[herb]["symptoms"].append(rec["symptom"])

            # 路径2：查询有处方的药材和方剂
            result = s.run(
                """
                MATCH (h:Herb)-[:TREATS]->(sy:Symptom)
                WHERE sy.name CONTAINS $keyword
                MATCH (p:Prescription)-[:CONTAINS]->(h)
                MATCH (f:Formula)-[:HAS_PRESCRIPTION]->(p)
                RETURN h.name AS herb, h.smell AS smell, h.cure AS cure,
                       f.name AS formula, f.functions AS functions,
                       sy.name AS symptom, 'formula' AS source
                LIMIT 15
                """,
                keyword=symptom,
            )
            for rec in result:
                herb = rec["herb"]
                formula = rec["formula"]
                if herb not in herbs_map:
                    herbs_map[herb] = {
                        "name": herb,
                        "smell": rec["smell"],
                        "cure": rec["cure"],
                        "symptoms": [],
                        "source": "formula",
                    }
                if rec["symptom"] not in herbs_map[herb]["symptoms"]:
                    herbs_map[herb]["symptoms"].append(rec["symptom"])

                if formula not in formulas_map:
                    formulas_map[formula] = {
                        "name": formula,
                        "functions": rec["functions"],
                        "herbs": [],
                    }
                if herb not in [h["name"] for h in formulas_map[formula]["herbs"]]:
                    formulas_map[formula]["herbs"].append({
                        "name": herb,
                        "smell": rec["smell"],
                    })

    return {
        "herbs": list(herbs_map.values()),
        "formulas": list(formulas_map.values()),
    }


# 供 Cypher 模板直接调用（仅允许只读查询）
_ALLOWED_PREFIXES = ("MATCH", "RETURN", "WITH", "CALL", "UNWIND")

def run_cypher(query: str, params: dict = None) -> List[Dict[str, Any]]:
    """执行只读 Cypher 查询（禁止写操作）"""
    stripped = query.strip().upper()
    if not any(stripped.startswith(p) for p in _ALLOWED_PREFIXES):
        raise ValueError(f"run_cypher 仅允许只读查询，拒绝: {query[:80]}...")
    # 禁止危险关键字
    for kw in ("DELETE", "DETACH", "CREATE", "SET", "REMOVE", "MERGE", "DROP"):
        if kw in stripped:
            raise ValueError(f"run_cypher 禁止写操作关键字: {kw}")
    driver = get_driver()
    with driver.session() as s:
        result = s.run(query, **(params or {}))
        return [dict(rec) for rec in result]
