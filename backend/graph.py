import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
from neo4j import GraphDatabase


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com"

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _run_write(session, func, *args):
    if hasattr(session, "execute_write"):
        return session.execute_write(func, *args)
    return session.write_transaction(func, *args)


def _run_read(session, func, *args):
    if hasattr(session, "execute_read"):
        return session.execute_read(func, *args)
    return session.read_transaction(func, *args)


def insert_triples(triples: Iterable[Any]) -> None:
    with driver.session() as session:
        for triple in triples:
            session.run(
                """
                MERGE (s:Entity {name: $subject})
                MERGE (o:Entity {name: $object})
                MERGE (s)-[:RELATION {type: $predicate}]->(o)
                """,
                subject=triple.subject,
                predicate=triple.predicate,
                object=triple.object
            )


def fetch_graph(limit: int = 100) -> List[Dict[str, Any]]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (s)-[r]->(o)
            RETURN s.name AS source, r.type AS relation, o.name AS target
            LIMIT $limit
            """,
            limit=limit
        )
        return [record.data() for record in result]


def _clear_user_graph(tx, user_id: str, tenant_id: str) -> None:
    tx.run(
        """
        MATCH (n)
        WHERE n.user_id = $user_id
          AND n.tenant_id = $tenant_id
        DETACH DELETE n
        """,
        user_id=user_id,
        tenant_id=tenant_id
    )


def _merge_contexts(
    tx,
    contexts: List[Dict[str, Any]],
    user_id: str,
    tenant_id: str
) -> None:
    tx.run(
        """
        UNWIND $contexts AS ctx
        WITH ctx,
             coalesce(ctx.document_id, "DOC-UNKNOWN") AS doc_id,
             coalesce(ctx.document_title, ctx.document_id, "DOC-UNKNOWN") AS doc_title
        MERGE (d:Document {document_id: doc_id, user_id: $user_id, tenant_id: $tenant_id})
        SET d.title = doc_title
        MERGE (c:Context {context_id: ctx.context_id, user_id: $user_id, tenant_id: $tenant_id})
        SET c.title_en = ctx.title_en,
            c.title_zh = ctx.title_zh,
            c.context_intents = ctx.context_intents,
            c.confidence_score = ctx.confidence_score,
            c.source_note = ctx.source_note,
            c.document_id = doc_id,
            c.document_title = doc_title
        MERGE (d)-[:HAS_CONTEXT]->(c)
        FOREACH (entity IN [e IN ctx.entities WHERE toLower(coalesce(e.type, "")) CONTAINS "role"] |
          MERGE (r:Role {name: entity.name, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (c)-[:AFFECTS_ROLE]->(r)
        )
        FOREACH (entity IN [e IN ctx.entities WHERE NOT toLower(coalesce(e.type, "")) CONTAINS "role"] |
          MERGE (e:Entity {name: entity.name, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (c)-[:HAS_ENTITY]->(e)
        )
        FOREACH (condition IN ctx.conditions |
          MERGE (cond:Condition {name: condition, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (cond)-[:SHAPES]->(c)
        )
        FOREACH (issue IN ctx.observed_issues |
          MERGE (i:Issue {name: issue, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (i)-[:IMPACTS]->(c)
        )
        FOREACH (outcome IN ctx.outcomes |
          MERGE (o:Outcome {name: outcome, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (c)-[:LEADS_TO]->(o)
        )
        FOREACH (solution IN ctx.recommended_solutions |
          MERGE (s:Solution {name: solution, user_id: $user_id, tenant_id: $tenant_id})
          MERGE (c)-[:MITIGATED_BY]->(s)
        )
        FOREACH (boundary IN ctx.decision_boundaries |
          MERGE (b:DecisionBoundary {
            boundary_type: boundary.boundary_type,
            user_id: $user_id,
            tenant_id: $tenant_id
          })
          SET b.description = boundary.description
          MERGE (c)-[:HAS_BOUNDARY]->(b)
        )
        """,
        contexts=contexts,
        user_id=user_id,
        tenant_id=tenant_id
    )


def _to_dict(context: Any) -> Dict[str, Any]:
    if hasattr(context, "model_dump"):
        return context.model_dump()
    if hasattr(context, "dict"):
        return context.dict()
    if isinstance(context, dict):
        return context
    return {}


def import_contexts(
    contexts: Iterable[Any],
    user_id: str,
    tenant_id: Optional[str] = None
) -> int:
    tenant = tenant_id or "public"
    normalized: List[Dict[str, Any]] = []

    for ctx in contexts:
        record = _to_dict(ctx)
        context_id = record.get("context_id")
        if not context_id:
            continue
        title = record.get("title") or {}
        if isinstance(title, dict):
            title_en = title.get("en") or ""
            title_zh = title.get("zh") or ""
        else:
            title_en = str(title)
            title_zh = ""
        normalized.append({
            "document_id": record.get("document_id"),
            "document_title": record.get("document_title"),
            "context_id": context_id,
            "title_en": title_en,
            "title_zh": title_zh,
            "context_intents": record.get("context_intents") or [],
            "entities": record.get("entities") or [],
            "conditions": record.get("conditions") or [],
            "observed_issues": record.get("observed_issues") or [],
            "outcomes": record.get("outcomes") or [],
            "recommended_solutions": record.get("recommended_solutions") or [],
            "decision_boundaries": record.get("decision_boundaries") or [],
            "confidence_score": record.get("confidence_score", 0.0),
            "source_note": record.get("source_note", "")
        })

    with driver.session() as session:
        _run_write(session, _clear_user_graph, user_id, tenant)
        if normalized:
            _run_write(session, _merge_contexts, normalized, user_id, tenant)

    return len(normalized)


def _node_identity(node) -> Tuple[str, str, str]:
    labels = set(node.labels)
    props = dict(node)
    fallback_id = getattr(node, "element_id", None) or str(getattr(node, "id", ""))

    if "Context" in labels:
        value = props.get("context_id") or ""
        node_id = f"context:{value}" if value else f"context:{fallback_id}"
        return node_id, "context", value or "Context"
    if "Document" in labels:
        value = props.get("document_id") or ""
        label = props.get("title") or value or "Document"
        node_id = f"document:{value}" if value else f"document:{fallback_id}"
        return node_id, "document", label
    if "Condition" in labels:
        value = props.get("name") or props.get("label") or ""
        node_id = f"condition:{value}" if value else f"condition:{fallback_id}"
        return node_id, "condition", value or "Condition"
    if "Issue" in labels:
        value = props.get("name") or props.get("label") or ""
        node_id = f"issue:{value}" if value else f"issue:{fallback_id}"
        return node_id, "issue", value or "Issue"
    if "Outcome" in labels:
        value = props.get("name") or props.get("label") or ""
        node_id = f"outcome:{value}" if value else f"outcome:{fallback_id}"
        return node_id, "outcome", value or "Outcome"
    if "Solution" in labels:
        value = props.get("name") or props.get("label") or ""
        node_id = f"solution:{value}" if value else f"solution:{fallback_id}"
        return node_id, "solution", value or "Solution"
    if "Role" in labels:
        value = props.get("name") or props.get("label") or ""
        node_id = f"role:{value}" if value else f"role:{fallback_id}"
        return node_id, "role", value or "Role"
    if "DecisionBoundary" in labels:
        value = props.get("description") or props.get("boundary_type") or ""
        node_id = f"boundary:{fallback_id}"
        return node_id, "decision_boundary", value or "Decision Boundary"
    if "Decision_boundary" in labels:
        value = props.get("label") or props.get("id") or ""
        node_id = props.get("id") or f"boundary:{fallback_id}"
        return node_id, "decision_boundary", value or "Decision Boundary"

    return f"node:{fallback_id}", "entity", props.get("name", "Entity")


def _link_label(
    rel_type: str,
    source: Dict[str, str],
    target: Dict[str, str]
) -> str:
    if rel_type == "SHAPES" and source["type"] == "condition":
        return f"Condition: {source['label']}"
    if rel_type == "IMPACTS" and source["type"] == "issue":
        return f"Issue: {source['label']}"
    if rel_type == "LEADS_TO" and target["type"] == "outcome":
        return f"Leads to: {target['label']}"
    if rel_type == "MITIGATED_BY" and target["type"] == "solution":
        return f"Mitigated by: {target['label']}"
    if rel_type == "HAS_CONTEXT" and target["type"] == "context":
        return "Document context"
    if rel_type == "HAS_ENTITY" and target["type"] == "entity":
        return "Involves entity"
    if rel_type == "AFFECTS_ROLE" and target["type"] == "role":
        return "Affects role"
    if rel_type == "HAS_BOUNDARY" and target["type"] == "decision_boundary":
        return "Decision boundary"
    return rel_type.replace("_", " ").title()


def fetch_decision_graph(
    user_id: str,
    tenant_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> Dict[str, Any]:
    tenant = tenant_id or "public"
    nodes: Dict[str, Dict[str, str]] = {}
    links: List[Dict[str, str]] = []
    link_keys = set()

    def add_node(node) -> Dict[str, str]:
        node_id, node_type, label = _node_identity(node)
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label
            }
        return nodes[node_id]

    with driver.session() as session:
        context_nodes = session.run(
            """
            MATCH (c:Context {user_id: $user_id})
            WHERE c.tenant_id = $tenant_id
              AND ($context_id IS NULL OR c.context_id = $context_id)
            RETURN c
            """,
            user_id=user_id,
            tenant_id=tenant,
            context_id=context_id
        )
        for record in context_nodes:
            add_node(record["c"])

        records = session.run(
            """
            MATCH (n)-[r]->(m)
            WHERE n.user_id = $user_id
              AND m.user_id = $user_id
              AND n.tenant_id = $tenant_id
              AND m.tenant_id = $tenant_id
              AND (
                $context_id IS NULL
                OR (n:Context AND n.context_id = $context_id)
                OR (m:Context AND m.context_id = $context_id)
              )
            RETURN n, r, m
            """,
            user_id=user_id,
            tenant_id=tenant,
            context_id=context_id
        )

        for record in records:
            source = add_node(record["n"])
            target = add_node(record["m"])
            rel = record["r"]
            label = _link_label(rel.type, source, target)
            key = (source["id"], target["id"], label)
            if key in link_keys:
                continue
            link_keys.add(key)
            links.append({
                "source": source["id"],
                "target": target["id"],
                "label": label
            })

    return {
        "nodes": list(nodes.values()),
        "links": links
    }
