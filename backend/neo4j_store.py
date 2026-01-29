import os
import re
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

from context_graph import build_decision_graph

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "contexture_neo4j_pass")

driver = GraphDatabase.driver(
    NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
)


def _safe_rel(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", label).upper()


def store_decision_graph(
    user_id: str,
    project_id: str,
    document_id: str,
    graph_id: str,
    contexts: List[Dict[str, Any]],
    tenant_id: Optional[str] = None
) -> None:
    tenant = tenant_id or user_id
    with driver.session() as session:
        session.run(
            """
            MERGE (u:User {user_id: $user_id, tenant_id: $tenant_id})
            MERGE (p:Project {project_id: $project_id, user_id: $user_id, tenant_id: $tenant_id})
            MERGE (d:Document {document_id: $document_id, user_id: $user_id, tenant_id: $tenant_id})
            SET d.graph_id = $graph_id
            MERGE (u)-[:HAS_PROJECT]->(p)
            MERGE (p)-[:HAS_DOCUMENT]->(d)
            """,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
            graph_id=graph_id,
            tenant_id=tenant
        )

        for context in contexts:
            context_id = context.get("context_id")
            if not context_id:
                continue
            context_node_id = f"context:{context_id}"
            context_label = context.get("title") or context_id
            if isinstance(context_label, dict):
                context_label = context_label.get("en") or context_label.get("zh") or context_id
            session.run(
                """
                MERGE (c:Context {context_id: $cid, user_id: $user_id, tenant_id: $tenant_id})
                SET c.document_id = $doc,
                    c.graph_id = $graph_id,
                    c.id = $node_id,
                    c.label = $label
                WITH c
                MATCH (d:Document {document_id: $doc, user_id: $user_id, tenant_id: $tenant_id})
                MERGE (d)-[:HAS_CONTEXT]->(c)
                """,
                cid=context_id,
                user_id=user_id,
                doc=document_id,
                graph_id=graph_id,
                tenant_id=tenant,
                node_id=context_node_id,
                label=str(context_label)
            )

            graph = build_decision_graph(context, contexts)

            for node in graph["nodes"]:
                node_type = str(node["type"]).capitalize()
                node_id = node["id"]
                node_label = node.get("label", "")
                context_ref = None
                if node_type.lower() == "context" and node_id.startswith("context:"):
                    context_ref = node_id.split("context:", 1)[1]
                session.run(
                    f"""
                    MERGE (n:{node_type} {{id: $id, user_id: $user_id, tenant_id: $tenant_id}})
                    SET n.label = $label,
                        n.document_id = $doc,
                        n.project_id = $project_id,
                        n.graph_id = $graph_id,
                        n.context_id = coalesce(n.context_id, $context_id)
                    """,
                    id=node_id,
                    user_id=user_id,
                    doc=document_id,
                    project_id=project_id,
                    graph_id=graph_id,
                    label=node_label,
                    tenant_id=tenant,
                    context_id=context_ref
                )

            for link in graph["links"]:
                rel_type = _safe_rel(link["label"])
                session.run(
                    f"""
                    MATCH (a {{id: $src, user_id: $user_id, tenant_id: $tenant_id}})
                    MATCH (b {{id: $dst, user_id: $user_id, tenant_id: $tenant_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.reason = $reason, r.graph_id = $graph_id
                    """,
                    src=link["source"],
                    dst=link["target"],
                    user_id=user_id,
                    reason=link.get("reason", ""),
                    graph_id=graph_id,
                    tenant_id=tenant
                )


def load_contexts_from_db(
    user_id: str,
    limit: Optional[int] = None,
    tenant_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    contexts: Dict[str, Dict[str, Any]] = {}
    tenant = tenant_id or user_id
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Context {user_id: $user_id, tenant_id: $tenant_id})
            RETURN c.context_id AS id, c.document_id AS document_id
            """,
            user_id=user_id,
            tenant_id=tenant
        )
        for record in result:
            contexts[record["id"]] = {
                "context_id": record["id"],
                "document_id": record["document_id"],
                "title": {"en": record["id"], "zh": record["id"]},
                "conditions": [],
                "observed_issues": [],
                "outcomes": [],
                "decision_boundaries": []
            }

        result = session.run(
            """
            MATCH (c:Context {user_id: $user_id, tenant_id: $tenant_id})-[:HAS_BOUNDARY]->(b:Decision_boundary)
            RETURN c.context_id AS cid, b.id AS btype, b.label AS desc
            """,
            user_id=user_id,
            tenant_id=tenant
        )
        for record in result:
            if record["cid"] in contexts:
                contexts[record["cid"]]["decision_boundaries"].append({
                    "boundary_type": record["btype"],
                    "description": record["desc"]
                })

        result = session.run(
            """
            MATCH (c:Context {user_id: $user_id, tenant_id: $tenant_id})-[r]->(n)
            WHERE type(r) IN ["condition", "issue", "outcome", "CONDITION", "ISSUE", "OUTCOME"]
            RETURN c.context_id AS cid, type(r) AS rel, n.label AS label
            """,
            user_id=user_id,
            tenant_id=tenant
        )
        for record in result:
            cid = record["cid"]
            if cid not in contexts:
                continue
            rel = record["rel"].upper()
            if rel == "CONDITION":
                contexts[cid]["conditions"].append(record["label"])
            elif rel == "ISSUE":
                contexts[cid]["observed_issues"].append(record["label"])
            elif rel == "OUTCOME":
                contexts[cid]["outcomes"].append(record["label"])

    results = list(contexts.values())
    if limit:
        return results[:limit]
    return results
