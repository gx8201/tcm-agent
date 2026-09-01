"""
中医知识图谱数据导入脚本

数据源：
1. ChineseMedicalQA (198⭐) - 670 味药材基础数据
2. Knowlegde_Graph_TCM (106⭐) - 中药 + 方剂关系数据
3. RenShu-AI sample_data - 演示医案和古籍

目标：Neo4j 5.26.4 (bolt://localhost:7687)
"""

import json
import os
from neo4j import GraphDatabase

# Neo4j 连接配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
if not NEO4J_PASSWORD:
    print("警告: NEO4J_PASSWORD 未设置，数据导入将失败")

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), "data-prep")


def load_herb_data():
    """加载 ChineseMedicalQA 药材数据"""
    herbs = []
    names_file = os.path.join(DATA_DIR, "cmqa", "name.txt")
    alias_file = os.path.join(DATA_DIR, "cmqa", "alias.txt")
    smell_file = os.path.join(DATA_DIR, "cmqa", "smell.txt")
    cure_file = os.path.join(DATA_DIR, "cmqa", "cure.txt")

    with open(names_file, encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    with open(alias_file, encoding="utf-8") as f:
        aliases = [line.strip() for line in f if line.strip()]
    with open(smell_file, encoding="utf-8") as f:
        smells = [line.strip() for line in f if line.strip()]
    with open(cure_file, encoding="utf-8") as f:
        cures = [line.strip() for line in f if line.strip()]

    for i in range(min(len(names), len(aliases), len(smells), len(cures))):
        if names[i]:
            herbs.append({
                "name": names[i],
                "alias": aliases[i] if i < len(aliases) else "",
                "smell": smells[i] if i < len(smells) else "",
                "cure": cures[i] if i < len(cures) else "",
            })
    return herbs


def load_kg_zhongyao_nodes():
    """加载 Knowlegde_Graph_TCM 中药节点"""
    nodes_file = os.path.join(DATA_DIR, "kg", "zhongyao_nodes.txt")
    herbs = {}
    current_herb = None

    with open(nodes_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            key, value = parts[0], parts[1]

            if key == "中药名":
                current_herb = value
                if current_herb not in herbs:
                    herbs[current_herb] = {"name": current_herb, "aliases": [], "indications": [], "functions": [], "distributions": []}
            elif current_herb:
                if key == "别名":
                    herbs[current_herb]["aliases"].append(value)
                elif key == "主治":
                    herbs[current_herb]["indications"].append(value)
                elif key == "功能":
                    herbs[current_herb]["functions"].append(value)
                elif key == "分布":
                    herbs[current_herb]["distributions"].append(value)
    return herbs


def load_kg_zhongyao_relations():
    """加载 Knowlegde_Graph_TCM 中药关系"""
    rels_file = os.path.join(DATA_DIR, "kg", "zhongyao_relations.json")
    with open(rels_file, encoding="utf-8") as f:
        return json.load(f)


def load_kg_fangji_nodes():
    """加载 Knowlegde_Graph_TCM 方剂节点"""
    nodes_file = os.path.join(DATA_DIR, "kg", "fangji_nodes.txt")
    formulas = {}
    current_formula = None
    current_prescription = None

    with open(nodes_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            key, value = parts[0], parts[1]

            if key == "方名":
                current_formula = value
                current_prescription = None
                if current_formula not in formulas:
                    formulas[current_formula] = {
                        "name": current_formula,
                        "prescriptions": [],
                        "functions": [],
                    }
            elif current_formula:
                if key == "处方":
                    current_prescription = {"id": value, "herbs": []}
                    formulas[current_formula]["prescriptions"].append(current_prescription)
                elif key == "中药名" and current_prescription:
                    current_prescription["herbs"].append({"name": value, "dose": ""})
                elif key == "剂量" and current_prescription and current_prescription["herbs"]:
                    current_prescription["herbs"][-1]["dose"] = value
                elif key == "功能主治":
                    formulas[current_formula]["functions"].append(value)
    return formulas


def load_kg_fangji_relations():
    """加载 Knowlegde_Graph_TCM 方剂关系"""
    rels_file = os.path.join(DATA_DIR, "kg", "fangji_relations.json")
    with open(rels_file, encoding="utf-8") as f:
        return json.load(f)


def import_to_neo4j():
    """导入所有数据到 Neo4j"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # 清空数据库
        print("清空数据库...")
        session.run("MATCH (n) DETACH DELETE n")

        # 创建索引
        print("创建索引...")
        session.run("CREATE INDEX IF NOT EXISTS FOR (h:Herb) ON (h.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (f:Formula) ON (f.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (s:Symptom) ON (s.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (p:Prescription) ON (p.id)")

        # 1. 导入 ChineseMedicalQA 药材数据
        print("\n1. 导入 ChineseMedicalQA 药材数据...")
        herbs = load_herb_data()
        for herb in herbs:
            session.run(
                """
                MERGE (h:Herb {name: $name})
                SET h.alias = $alias, h.smell = $smell, h.cure = $cure, h.source = 'ChineseMedicalQA'
                """,
                name=herb["name"],
                alias=herb["alias"],
                smell=herb["smell"],
                cure=herb["cure"],
            )
        print(f"   导入 {len(herbs)} 味药材")

        # 2. 导入 Knowlegde_Graph_TCM 中药节点（补充别名、主治等）
        print("\n2. 导入 Knowlegde_GGraph_TCM 中药数据...")
        kg_herbs = load_kg_zhongyao_nodes()
        count = 0
        for name, data in kg_herbs.items():
            session.run(
                """
                MERGE (h:Herb {name: $name})
                SET h.kg_alias = $aliases,
                    h.kg_indications = $indications,
                    h.kg_functions = $functions,
                    h.source_kg = 'Knowlegde_Graph_TCM'
                """,
                name=name,
                aliases=data["aliases"],
                indications=data["indications"],
                functions=data["functions"],
            )
            count += 1
        print(f"   更新/创建 {count} 味中药")

        # 3. 导入 Knowlegde_Graph_TCM 中药关系（主治、分布）
        print("\n3. 导入中药关系...")
        zhongyao_rels = load_kg_zhongyao_relations()
        rel_count = 0
        for rel in zhongyao_rels:
            node1_parts = rel["node_1"].split("\t")
            node2_parts = rel["node_2"].split("\t")
            rel_type = rel["relation"]

            if len(node1_parts) < 2 or len(node2_parts) < 2:
                continue

            n1_label, n1_name = node1_parts[0], node1_parts[1]
            n2_label, n2_name = node2_parts[0], node2_parts[1]

            if rel_type == "attending":
                # 主治关系：Herb -[:TREATS]-> Symptom
                session.run(
                    """
                    MERGE (h:Herb {name: $herb})
                    MERGE (s:Symptom {name: $symptom})
                    MERGE (h)-[:TREATS]->(s)
                    """,
                    herb=n1_name,
                    symptom=n2_name,
                )
                rel_count += 1
            elif rel_type == "distribution area":
                # 分布关系：Herb -[:DISTRIBUTED_IN]-> Region
                session.run(
                    """
                    MERGE (h:Herb {name: $herb})
                    MERGE (r:Region {name: $region})
                    MERGE (h)-[:DISTRIBUTED_IN]->(r)
                    """,
                    herb=n1_name,
                    region=n2_name,
                )
                rel_count += 1
        print(f"   导入 {rel_count} 条中药关系")

        # 4. 导入方剂数据
        print("\n4. 导入方剂数据...")
        formulas = load_kg_fangji_nodes()
        for fname, fdata in formulas.items():
            # 创建方剂节点
            session.run(
                """
                MERGE (f:Formula {name: $name})
                SET f.functions = $functions
                """,
                name=fname,
                functions=fdata["functions"],
            )

            # 创建处方和药材关系
            for presc in fdata["prescriptions"]:
                session.run(
                    """
                    MERGE (p:Prescription {id: $pid})
                    MERGE (f:Formula {name: $fname})
                    MERGE (f)-[:HAS_PRESCRIPTION]->(p)
                    """,
                    pid=presc["id"],
                    fname=fname,
                )
                for herb in presc["herbs"]:
                    session.run(
                        """
                        MERGE (h:Herb {name: $herb})
                        MERGE (p:Prescription {id: $pid})
                        MERGE (p)-[:CONTAINS {dose: $dose}]->(h)
                        """,
                        herb=herb["name"],
                        pid=presc["id"],
                        dose=herb["dose"],
                    )
        print(f"   导入 {len(formulas)} 个方剂")

        # 5. 导入方剂关系（证型-方剂对应）
        print("\n5. 导入方剂关系...")
        fangji_rels = load_kg_fangji_relations()
        fj_rel_count = 0
        for rel in fangji_rels:
            node1_parts = rel["node_1"].split("\t")
            node2_parts = rel["node_2"].split("\t")
            rel_type = rel["relation"]

            if len(node1_parts) < 2 or len(node2_parts) < 2:
                continue

            n1_label, n1_name = node1_parts[0], node1_parts[1]
            n2_label, n2_name = node2_parts[0], node2_parts[1]

            if n1_label == "功能主治" and n2_label == "方名":
                # 方剂功能主治
                session.run(
                    """
                    MERGE (f:Formula {name: $fname})
                    SET f.functions = coalesce(f.functions, []) + $func
                    """,
                    fname=n2_name,
                    func=n1_name,
                )
                fj_rel_count += 1
        print(f"   处理 {fj_rel_count} 条方剂关系")

        # 6. 导入 RenShu-AI 演示数据
        print("\n6. 导入 RenShu-AI 演示数据...")
        cases_file = os.path.join(DATA_DIR, "cases.json")
        classics_file = os.path.join(DATA_DIR, "classics.json")

        if os.path.exists(cases_file):
            with open(cases_file, encoding="utf-8") as f:
                cases = json.load(f)
            for case in cases:
                session.run(
                    """
                    MERGE (c:Case {id: $id})
                    SET c.symptoms = $symptoms,
                        c.diagnosis = $diagnosis,
                        c.treatment = $treatment
                    """,
                    id=case.get("id", ""),
                    symptoms=case.get("symptoms", []),
                    diagnosis=case.get("diagnosis", ""),
                    treatment=case.get("treatment", ""),
                )
            print(f"   导入 {len(cases)} 个医案")

        if os.path.exists(classics_file):
            with open(classics_file, encoding="utf-8") as f:
                classics = json.load(f)
            for classic in classics:
                session.run(
                    """
                    MERGE (c:Classic {id: $id})
                    SET c.title = $title,
                        c.content = $content,
                        c.source = $source
                    """,
                    id=classic.get("id", ""),
                    title=classic.get("title", ""),
                    content=classic.get("content", ""),
                    source=classic.get("source", ""),
                )
            print(f"   导入 {len(classics)} 条古籍")

        # 7. 验证导入结果
        print("\n" + "=" * 50)
        print("导入完成！验证结果：")
        result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC")
        for record in result:
            print(f"  {record['label']}: {record['cnt']} 个节点")

        result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt ORDER BY cnt DESC")
        for record in result:
            print(f"  {record['type']}: {record['cnt']} 条关系")

    driver.close()
    print("\n✅ Neo4j 数据导入完成！")


if __name__ == "__main__":
    import_to_neo4j()
