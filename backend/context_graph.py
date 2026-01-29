import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_TEST_FILE = "test2.json"


def _safe_data_path(filename: Optional[str]) -> Optional[Path]:
    if not filename:
        filename = DEFAULT_TEST_FILE
    if not filename.endswith(".json"):
        return None
    candidate = (DATA_DIR / filename).resolve()
    if DATA_DIR not in candidate.parents:
        return None
    return candidate


def _resolve_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or value.get("zh") or "").strip()
    if value is None:
        return ""
    return str(value).strip()


def _load_raw_payload(data_file: Optional[str]) -> Optional[Any]:
    path = _safe_data_path(data_file)
    if not path or not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return None


def _normalize_source_note(value: Any) -> str:
    if isinstance(value, dict):
        section = str(value.get("section") or "").strip()
        page = str(value.get("page") or "").strip()
        if section and page:
            return f"{section}, p.{page}"
        return section or page
    return _resolve_text(value)


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_context(
    raw: Dict[str, Any],
    document_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    document_meta = document_meta or {}
    title = raw.get("title") or raw.get("title_text") or {}
    if isinstance(title, str):
        title = {"en": title}
    if not title:
        inferred = raw.get("context_type") or raw.get("scenario_summary") or raw.get("context_id")
        title = {"en": _resolve_text(inferred)}

    intents = _ensure_list(
        raw.get("context_intents") or raw.get("context_type") or raw.get("context_scope")
    )
    intent_values = [str(item) for item in intents if item]

    decision_boundaries = []
    for boundary in _ensure_list(raw.get("decision_boundaries")):
        if not isinstance(boundary, dict):
            continue
        decision_boundaries.append({
            "boundary_type": boundary.get("boundary_type", "unspecified"),
            "description": boundary.get("description", ""),
            "affected_roles": boundary.get("affected_roles") or []
        })

    return {
        "context_id": raw.get("context_id", ""),
        "decision_level": raw.get("decision_level"),
        "title": title,
        "context_intents": intent_values,
        "entities": _ensure_list(raw.get("entities")),
        "conditions": _ensure_list(raw.get("conditions")),
        "observed_issues": _ensure_list(
            raw.get("observed_issues") or raw.get("observed_issues_or_risks")
        ),
        "outcomes": _ensure_list(
            raw.get("outcomes") or raw.get("outcomes_or_consequences")
        ),
        "recommended_solutions": _ensure_list(raw.get("recommended_solutions")),
        "decision_boundaries": decision_boundaries,
        "counterfactuals": _ensure_list(raw.get("counterfactuals")),
        "confidence_score": float(raw.get("confidence_score") or 0.0),
        "source_note": _normalize_source_note(
            raw.get("source_note") or raw.get("source_reference")
        ),
        "llm_usage_policy": raw.get("llm_usage_policy"),
        "document_id": raw.get("document_id") or document_meta.get("document_id"),
        "document_title": raw.get("document_title") or document_meta.get("document_title"),
        "document_metadata": document_meta,
        "evolves_to": _ensure_list(raw.get("evolves_to"))
    }


def _extract_document_meta(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        meta = payload.get("document_metadata")
        if isinstance(meta, dict):
            return {
                "document_id": meta.get("document_id"),
                "document_title": meta.get("document_title"),
                "document_type": meta.get("document_type"),
                "vendor": meta.get("vendor"),
                "product": meta.get("product"),
                "version": meta.get("version")
            }
    return {}


def _extract_contexts_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("contexts"), list):
            return payload.get("contexts", [])
        if isinstance(payload.get("context_nodes"), list):
            return payload.get("context_nodes", [])
    if isinstance(payload, list):
        return payload
    return []


def load_contexts(
    mode: str = "test",
    data_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    if mode != "test":
        return []

    payload = _load_raw_payload(data_file)
    if payload is None:
        return []

    document_meta = _extract_document_meta(payload)
    raw_contexts = _extract_contexts_from_payload(payload)
    return [
        _normalize_context(raw, document_meta=document_meta)
        for raw in raw_contexts
        if isinstance(raw, dict)
    ]


def list_testing_files() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not DATA_DIR.exists():
        return results

    for file in sorted(DATA_DIR.glob("*.json")):
        if file.name.startswith("upload"):
            continue
        payload = _load_raw_payload(file.name)
        if payload is None:
            continue
        document_meta = _extract_document_meta(payload)
        raw_contexts = _extract_contexts_from_payload(payload)
        title = (
            document_meta.get("document_title")
            or document_meta.get("document_id")
            or file.stem
        )
        results.append({
            "file": file.name,
            "document_id": document_meta.get("document_id") or file.stem,
            "document_title": title,
            "context_count": len(raw_contexts)
        })

    return results


def get_context_by_id(
    context_id: str,
    mode: str = "test",
    data_file: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    contexts = load_contexts(mode=mode, data_file=data_file)
    for context in contexts:
        if context.get("context_id") == context_id:
            return context
    return None


def build_context_graph(context: Dict[str, Any]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, str]] = {}
    links: List[Dict[str, str]] = []

    def ensure_node(node_id: str, node_type: str, label: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label
            }

    context_id = str(context.get("context_id", "")).strip()
    if not context_id:
        return {"nodes": [], "links": []}

    context_title = _resolve_text(context.get("title")) or context_id
    context_node_id = f"context:{context_id}"
    ensure_node(context_node_id, "context", context_title)

    for entity in context.get("entities", []):
        entity_name = str(entity.get("name", "")).strip()
        if not entity_name:
            continue
        entity_type = str(entity.get("type", "entity")).strip().lower()
        node_type = "role" if "role" in entity_type else "entity"
        entity_node_id = f"{node_type}:{entity_name}"
        ensure_node(entity_node_id, node_type, entity_name)
        links.append({
            "source": context_node_id,
            "target": entity_node_id,
            "label": str(entity.get("type", node_type))
        })

    for condition in context.get("conditions", []):
        condition_name = _resolve_text(condition)
        if not condition_name:
            continue
        condition_node_id = f"condition:{condition_name}"
        ensure_node(condition_node_id, "condition", condition_name)
        links.append({
            "source": context_node_id,
            "target": condition_node_id,
            "label": "condition"
        })

    for issue in context.get("observed_issues", []):
        issue_name = _resolve_text(issue)
        if not issue_name:
            continue
        issue_node_id = f"issue:{issue_name}"
        ensure_node(issue_node_id, "issue", issue_name)
        links.append({
            "source": context_node_id,
            "target": issue_node_id,
            "label": "issue"
        })

    for outcome in context.get("outcomes", []):
        outcome_name = _resolve_text(outcome)
        if not outcome_name:
            continue
        outcome_node_id = f"outcome:{outcome_name}"
        ensure_node(outcome_node_id, "outcome", outcome_name)
        links.append({
            "source": context_node_id,
            "target": outcome_node_id,
            "label": "outcome"
        })

    for solution in context.get("recommended_solutions", []):
        solution_name = _resolve_text(solution)
        if not solution_name:
            continue
        solution_node_id = f"solution:{solution_name}"
        ensure_node(solution_node_id, "solution", solution_name)
        links.append({
            "source": context_node_id,
            "target": solution_node_id,
            "label": "solution"
        })

    return {
        "nodes": list(nodes.values()),
        "links": links
    }


def build_decision_graph(
    context: Dict[str, Any],
    contexts: Optional[List[Dict[str, Any]]] = None,
    limit: int = 2
) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, str]] = {}
    links: List[Dict[str, str]] = []

    def ensure_node(node_id: str, node_type: str, label: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label
            }

    context_id = str(context.get("context_id", "")).strip()
    if not context_id:
        return {"nodes": [], "links": []}

    context_label = _resolve_text(context.get("title")) or context_id
    context_node_id = f"context:{context_id}"
    ensure_node(context_node_id, "context", context_label)

    for entity in context.get("entities", []):
        entity_name = str(entity.get("name", "")).strip()
        if not entity_name:
            continue
        entity_type = str(entity.get("type", "entity")).strip().lower()
        if "role" in entity_type:
            node_type = "role"
            link_label = "AFFECTS_ROLE"
        else:
            node_type = "entity"
            link_label = "INVOLVES_ENTITY"
        node_id = f"{node_type}:{entity_name}"
        ensure_node(node_id, node_type, entity_name)
        links.append({
            "source": context_node_id,
            "target": node_id,
            "label": link_label,
            "reason": str(entity.get("type", "")).strip()
        })

    for condition in context.get("conditions", []):
        condition_name = _resolve_text(condition)
        if not condition_name:
            continue
        condition_id = f"condition:{condition_name}"
        ensure_node(condition_id, "condition", condition_name)
        links.append({
            "source": context_node_id,
            "target": condition_id,
            "label": "CONDITION",
            "reason": condition_name
        })

    for issue in context.get("observed_issues", []):
        issue_name = _resolve_text(issue)
        if not issue_name:
            continue
        issue_id = f"issue:{issue_name}"
        ensure_node(issue_id, "issue", issue_name)
        links.append({
            "source": context_node_id,
            "target": issue_id,
            "label": "ISSUE",
            "reason": issue_name
        })

    for outcome in context.get("outcomes", []):
        outcome_name = _resolve_text(outcome)
        if not outcome_name:
            continue
        outcome_id = f"outcome:{outcome_name}"
        ensure_node(outcome_id, "outcome", outcome_name)
        links.append({
            "source": context_node_id,
            "target": outcome_id,
            "label": "OUTCOME",
            "reason": outcome_name
        })

    for boundary in context.get("decision_boundaries", []):
        if not isinstance(boundary, dict):
            continue
        boundary_type = str(boundary.get("boundary_type", "boundary")).strip()
        description = _resolve_text(boundary.get("description")) or boundary_type
        boundary_id = f"boundary:{context_id}:{boundary_type}"
        ensure_node(boundary_id, "decision_boundary", description)
        links.append({
            "source": context_node_id,
            "target": boundary_id,
            "label": "HAS_BOUNDARY",
            "reason": description
        })

    if contexts:
        for similar in build_similarity(context, contexts, limit=limit):
            other_id = similar.get("context_id")
            if not other_id:
                continue
            other_label = str(other_id)
            other_node_id = f"context:{other_id}"
            ensure_node(other_node_id, "context", other_label)
            links.append({
                "source": context_node_id,
                "target": other_node_id,
                "label": "SIMILAR_TO",
                "reason": f"{similar.get('score')} similarity"
            })

    for evolves_to in _ensure_list(context.get("evolves_to")):
        target_id = str(evolves_to).strip()
        if not target_id:
            continue
        target_node_id = f"context:{target_id}"
        ensure_node(target_node_id, "context", target_id)
        links.append({
            "source": context_node_id,
            "target": target_node_id,
            "label": "EVOLVES_TO",
            "reason": "Decision evolution"
        })

    return {
        "nodes": list(nodes.values()),
        "links": links
    }


def build_similarity(
    context: Dict[str, Any],
    contexts: List[Dict[str, Any]],
    limit: int = 3
) -> List[Dict[str, Any]]:
    def normalize(values: List[Any]) -> List[str]:
        return [item.lower() for item in (_resolve_text(v) for v in values) if item]

    base_conditions = set(normalize(context.get("conditions", [])))
    if not base_conditions:
        return []

    results: List[Dict[str, Any]] = []
    for other in contexts:
        if other.get("context_id") == context.get("context_id"):
            continue
        other_conditions = set(normalize(other.get("conditions", [])))
        if not other_conditions:
            continue
        shared = base_conditions.intersection(other_conditions)
        score = len(shared) / max(len(base_conditions), len(other_conditions))
        if score <= 0:
            continue

        if score >= 0.8:
            label = "Success"
        elif score >= 0.6:
            label = "Failure"
        else:
            label = "Irrelevant"

        results.append({
            "context_id": other.get("context_id"),
            "score": round(score, 2),
            "label": label
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
