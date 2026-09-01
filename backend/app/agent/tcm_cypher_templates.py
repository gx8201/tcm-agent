"""
TCM Cypher 查询模板

精简版：保留核心诊断查询模板，去除 Neo4j 执行逻辑
这些模板展示了知识图谱的查询结构，实际使用时需要连接 Neo4j
"""

# ============== 核心诊断查询模板 ==============

DIAGNOSIS_CYPHER_TEMPLATES = {
    # 症状 → 证候 查询
    "symptom_to_syndrome": {
        "single_symptom": {
            "description": "根据单个症状查询可能的证候",
            "cypher": """
                MATCH (s:Symptom)-[:INDICATES]->(syn:Syndrome)
                WHERE s.symptom = $symptom
                RETURN syn.syndrome AS 证候, COUNT(*) AS 关联度
                ORDER BY 关联度 DESC
            """,
            "parameters": ["symptom"],
        },
        "multiple_symptoms": {
            "description": "根据多个症状查询证候（核心诊断查询）",
            "cypher": """
                MATCH (s:Symptom)-[:INDICATES]->(syn:Syndrome)
                WHERE s.symptom IN $symptoms
                WITH syn, COUNT(DISTINCT s) AS match_count,
                     COLLECT(DISTINCT s.symptom) AS matched_symptoms
                ORDER BY match_count DESC
                LIMIT $limit
                RETURN syn.syndrome AS 证候, matched_symptoms AS 匹配症状,
                       match_count AS 匹配数量
            """,
            "parameters": ["symptoms", "limit"],
            "defaults": {"limit": 5},
        },
    },

    # 证候 → 方剂 查询
    "syndrome_to_formula": {
        "by_syndrome_name": {
            "description": "根据证候名称查询推荐方剂",
            "cypher": """
                MATCH (syn:Syndrome)-[:TREATS_WITH]->(f:Formula)
                WHERE syn.syndrome = $syndrome
                RETURN f.formula AS 方剂, syn.syndrome AS 证候
                LIMIT $limit
            """,
            "parameters": ["syndrome", "limit"],
            "defaults": {"limit": 10},
        },
    },

    # 完整诊断路径
    "diagnosis_path": {
        "full_path": {
            "description": "查询完整的诊断路径：症状 → 证候 → 方剂",
            "cypher": """
                MATCH (s:Symptom)-[:INDICATES]->(syn:Syndrome)-[:TREATS_WITH]->(f:Formula)
                WHERE s.symptom IN $symptoms
                WITH syn, COLLECT(DISTINCT s.symptom) AS matched_symptoms,
                     COLLECT(DISTINCT f.formula) AS formulas
                RETURN syn.syndrome AS 证候, matched_symptoms AS 匹配症状,
                       SIZE(matched_symptoms) AS 匹配数, formulas[0..5] AS 推荐方剂
                ORDER BY 匹配数 DESC
                LIMIT $limit
            """,
            "parameters": ["symptoms", "limit"],
            "defaults": {"limit": 5},
        },
    },
}


def get_diagnosis_template(category: str, template_name: str) -> dict | None:
    """获取诊断 Cypher 模板"""
    if category in DIAGNOSIS_CYPHER_TEMPLATES:
        if template_name in DIAGNOSIS_CYPHER_TEMPLATES[category]:
            return DIAGNOSIS_CYPHER_TEMPLATES[category][template_name]
    return None
