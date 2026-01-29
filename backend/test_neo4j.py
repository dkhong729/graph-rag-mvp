import json
from pathlib import Path
from typing import Dict, List

from neo4j import GraphDatabase

from context_graph import load_contexts, build_decision_graph

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = "test4.json"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "contexture_neo4j_pass"   

driver = GraphDatabase.driver(
    NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
)


def clear_db():
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("[OK] Neo4j cleared")


def write_decision_graph(
    document_id: str,
    context_id: str,
    graph: Dict[str, List[Dict]]
):
    with driver.session() as session:
        # Document
        session.run(
            """
            MERGE (d:Document {document_id: $doc})
            """,
            doc=document_id
        )

        # Context
        session.run(
            """
            MERGE (c:Context {context_id: $cid})
            SET c.document_id = $doc
            """,
            cid=context_id,
            doc=document_id
        )

        # Nodes
        for node in graph["nodes"]:
            session.run(
                f"""
                MERGE (n:{node['type'].capitalize()} {{id: $id}})
                SET n.label = $label
                """,
                id=node["id"],
                label=node.get("label", "")
            )

        # Edges
        for link in graph["links"]:
            session.run(
                f"""
                MATCH (a {{id: $src}})
                MATCH (b {{id: $dst}})
                MERGE (a)-[r:{link['label']}]->(b)
                SET r.reason = $reason
                """,
                src=link["source"],
                dst=link["target"],
                reason=link.get("reason", "")
            )

def list_documents():
    with driver.session() as session:
        result = session.run(
            "MATCH (d:Document) RETURN d.document_id AS id"
        )
        docs = [r["id"] for r in result]
    print("[Documents]", docs)
    return docs


def list_contexts(document_id: str):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Context {document_id: $doc})
            RETURN c.context_id AS id
            """,
            doc=document_id
        )
        ctxs = [r["id"] for r in result]
    print(f"[Contexts in {document_id}]", ctxs)
    return ctxs

if __name__ == "__main__":
    print("=== TEST NEO4J PIPELINE ===")

    clear_db()

    contexts = load_contexts(mode="test", data_file=DATA_FILE)
    print(f"[OK] Loaded {len(contexts)} contexts")

    for ctx in contexts:
        graph = build_decision_graph(ctx, contexts)
        write_decision_graph(
            document_id=ctx["document_id"],
            context_id=ctx["context_id"],
            graph=graph
        )

    docs = list_documents()
    if docs:
        list_contexts(docs[0])

