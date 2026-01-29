import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

sys.path.append(str(Path(__file__).resolve().parent))
from prompt_versions import (
    DOCUMENT_RENDER_VERSION,
    MEETING_RENDER_VERSION,
    PERSONA_EXTRACT_VERSION
)

STYLE_GUIDES = {
    "technical": "Prioritize engineering details, constraints, failure modes, and operational risks.",
    "business": "Prioritize trade-offs, cost impact, timeline, and organizational implications.",
    "executive": "Prioritize decisive conclusions, irreversible points, and concise executive takeaways."
}


def _ensure_llm():
    if ChatOpenAI is None:
        raise RuntimeError("langchain_openai is required for LLM pipelines.")
    return ChatOpenAI(
        model="deepseek-chat",
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        streaming=True
    )


def _build_document_prompt():
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a decision page renderer. Produce a decision page in HTML.\n"
                "Rules:\n"
                "- Only use provided document intelligence; do NOT invent facts.\n"
                "- Output HTML only, no Markdown.\n"
                "- Keep under {page_limit} A4 pages.\n"
                "- Style: {style} (technical | business | executive).\n"
                "- Style guidance: {style_guide}\n"
                "- Language: {language} (zh or en).\n"
                "- Must include sections for: Overview, Key Facts, Key Numbers, Core Results,\n"
                "  Assumptions, Dependencies, Uncertainties, Claims Requiring Validation.\n"
                "- Styles must only affect tone and visual density, NOT the structure.\n"
                f"- Prompt version: {DOCUMENT_RENDER_VERSION}\n"
            ),
            ("user", "Document intelligence JSON:\n{doc_intelligence}")
        ]
    )


def build_document_render_chain():
    llm = _ensure_llm()
    prompt = _build_document_prompt()

    def prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
        style = payload.get("style", "technical")
        return {
            "style": style,
            "style_guide": STYLE_GUIDES.get(style, STYLE_GUIDES["technical"]),
            "language": payload.get("language", "en"),
            "page_limit": payload.get("page_limit", 2),
            "doc_intelligence": json.dumps(payload.get("doc_intelligence", {}), ensure_ascii=False)
        }

    return RunnableLambda(prepare) | prompt | llm | StrOutputParser()


def build_meeting_chain():
    llm = _ensure_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a meeting decision page renderer. Output HTML only.\n"
                "Rules:\n"
                "- Keep under {page_limit} A4 pages.\n"
                "- Output must include three layers: Facts, Stances, Values.\n"
                "- Identify speakers and their worldview, risks, veto power.\n"
                "- Style: {style} (technical | business | executive).\n"
                "- Style guidance: {style_guide}\n"
                "- Language: {language} (zh or en).\n"
                f"- Prompt version: {MEETING_RENDER_VERSION}\n"
            ),
            ("user", "Meeting intelligence JSON:\n{meeting_intelligence}")
        ]
    )

    def prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
        style = payload.get("style", "executive")
        return {
            "meeting_intelligence": json.dumps(payload.get("meeting_intelligence", {}), ensure_ascii=False),
            "style": style,
            "style_guide": STYLE_GUIDES.get(style, STYLE_GUIDES["executive"]),
            "language": payload.get("language", "en"),
            "page_limit": payload.get("page_limit", 2)
        }

    return RunnableLambda(prepare) | prompt | llm | StrOutputParser()


def extract_personas_from_transcript(transcript: str) -> List[Dict[str, Any]]:
    llm = _ensure_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract meeting personas from transcript. Output JSON array only.\n"
                "Each item: {name, role, decision_style, values, risk_bias, veto_power}."
                f"\nPrompt version: {PERSONA_EXTRACT_VERSION}"
            ),
            ("user", "Transcript:\n{transcript}")
        ]
    )
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({"transcript": transcript})
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []
