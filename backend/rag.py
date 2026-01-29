import json
import os
import re
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None


def _ensure_llm():
    if ChatOpenAI is None:
        raise RuntimeError("langchain_openai is required for RAG.")
    return ChatOpenAI(
        model="deepseek-chat",
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())


def _score(query: str, context: Dict[str, Any]) -> float:
    tokens = set(_tokenize(query))
    bag = []
    for field in ["context_id", "conditions", "observed_issues", "outcomes"]:
        value = context.get(field)
        if isinstance(value, list):
            bag.extend([str(v) for v in value])
        else:
            bag.append(str(value or ""))
    for boundary in context.get("decision_boundaries", []):
        bag.append(str(boundary.get("boundary_type", "")))
        bag.append(str(boundary.get("description", "")))
    context_tokens = set(_tokenize(" ".join(bag)))
    if not tokens:
        return 0.0
    return len(tokens.intersection(context_tokens)) / len(tokens)


def select_contexts(query: str, contexts: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    scored = [(ctx, _score(query, ctx)) for ctx in contexts]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [ctx for ctx, _ in scored[:limit]]


def build_rag_chain(retriever):
    llm = _ensure_llm()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a decision assistant. Use ONLY the provided decision contexts.\n"
                "No hallucination. Cite context_id when referencing examples.\n"
                "Explain why a decision is risky or irreversible.\n"
                "Respond in the user's language: {language}.\n"
            ),
            (
                "user",
                "Question: {query}\n"
                "Decision contexts: {contexts}\n"
            )
        ]
    )

    return (
        RunnablePassthrough.assign(
            contexts=RunnableLambda(lambda x: json.dumps(retriever(x), ensure_ascii=False))
        )
        | prompt
        | llm
        | StrOutputParser()
    )
