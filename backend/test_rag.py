import os
import json
from typing import Dict, List, Any
from neo4j import GraphDatabase
from rag import answer_context_query

# ------------------------
# Neo4j config
# ------------------------
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "contexture_neo4j_pass"

driver = GraphDatabase.driver(
    NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
)

# ------------------------
# Load contexts from Neo4j
# ------------------------
# test_rag.py 檔案中的 load_contexts_from_db 函式

def load_contexts_from_db() -> List[Dict[str, Any]]:
    contexts: Dict[str, Dict[str, Any]] = {}

    with driver.session() as session:
        # 1. Context nodes (保持原樣)
        result = session.run("MATCH (c:Context) RETURN c.context_id AS id, c.document_id AS document_id")
        for r in result:
            contexts[r["id"]] = {
                "context_id": r["id"],
                "document_id": r["document_id"],
                "title": {"en": r["id"], "zh": r["id"]},
                "conditions": [],
                "observed_issues": [],
                "outcomes": [],
                "decision_boundaries": []
            }

        # 修正處 1: 標籤改為 Decision_boundary，屬性改為 id 與 label (對齊你先前的寫入邏輯)
        result = session.run(
            """
            MATCH (c:Context)-[:HAS_BOUNDARY]->(b:Decision_boundary)
            RETURN
              c.context_id AS cid,
              b.id AS btype,
              b.label AS desc
            """
        )
        for r in result:
            if r["cid"] in contexts:
                contexts[r["cid"]]["decision_boundaries"].append({
                    "boundary_type": r["btype"],
                    "description": r["desc"]
                })

        # 修正處 2: 關係名稱改為大寫 (對齊你剛才 log 顯示的寫入習慣)
        result = session.run(
            """
            MATCH (c:Context)-[r]->(n)
            WHERE type(r) IN ["condition", "issue", "outcome", "CONDITION", "ISSUE", "OUTCOME"]
            RETURN
              c.context_id AS cid,
              type(r) AS rel,
              n.label AS label
            """
        )
        for r in result:
            cid = r["cid"]
            if cid not in contexts: continue
            rel = r["rel"].upper() # 統一轉大寫處理
            if rel == "CONDITION":
                contexts[cid]["conditions"].append(r["label"])
            elif rel == "ISSUE":
                contexts[cid]["observed_issues"].append(r["label"])
            elif rel == "OUTCOME":
                contexts[cid]["outcomes"].append(r["label"])

    return list(contexts.values())

# ------------------------
# Test 1: Fact QA
# ------------------------
def test_fact_qa(contexts: List[Dict[str, Any]]):
    print("\n=== TEST 1: Fact QA ===")

    questions = [
        "PCI 擴充板會帶來什麼風險？",
        "哪些決策屬於 no second chance？",
        "如果電源中斷發生，系統會有什麼後果？"
    ]

    for q in questions:
        print(f"\n[Q] {q}")
        result = answer_context_query(
            query=q,
            contexts=contexts,
            language="zh"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

# ------------------------
# Test 2: Decision Support
# ------------------------
def test_decision_support(contexts: List[Dict[str, Any]]):
    print("\n=== TEST 2: Decision Support ===")

    decision_query = (
        "我現在要在工廠系統中新增一個 PCI 擴充模組，"
        "希望系統可以長時間穩定運作，"
        "請問有哪些相似的歷史決策？"
        "我需要注意哪些高風險或不可逆的地方？"
    )

    print(f"\n[Decision] {decision_query}")

    result = answer_context_query(
        query=decision_query,
        contexts=contexts,
        language="zh"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    print("=== LOAD CONTEXTS FROM NEO4J ===")
    contexts = load_contexts_from_db()
    print(f"[OK] Loaded {len(contexts)} contexts")

    test_fact_qa(contexts)
    test_decision_support(contexts)

