import os
import re
import sys
from pathlib import Path
import requests

sys.path.append(str(Path(__file__).resolve().parent))
from schemas import DocumentIntelligence, MeetingIntelligence
from prompt_versions import DOCUMENT_INTELLIGENCE_VERSION, MEETING_INTELLIGENCE_VERSION

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from dotenv import load_dotenv

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com"

DOCUMENT_INTELLIGENCE_PROMPT = f"""
SYSTEM PROMPT:

You are a Document Intelligence Extractor.
Your job is NOT to decide, NOT to summarize with opinions, and NOT to generate new facts.

Input may contain noisy language, emotions, greetings, emojis, and fluff.
You MUST remove all emotional or casual content and extract only:
facts, numbers, conclusions, assumptions, dependencies, uncertainties, and claims needing validation.

Return STRICT JSON ONLY with this schema:
{{
  "document_overview": {{
    "title": "...",
    "domain": "...",
    "primary_topic": "...",
    "timeframe": "...",
    "source_type": "report | paper | pitch | memo | transcript | other",
    "summary": "1-3 sentences, factual only"
  }},
  "key_facts": ["..."],
  "key_numbers": [
    {{ "label": "...", "value": "...", "context": "..." }}
  ],
  "core_results": ["..."],
  "assumptions": ["..."],
  "dependencies": ["..."],
  "uncertainties": ["..."],
  "claims_requiring_validation": ["..."]
}}

Rules:
- Facts must be verifiable from the input.
- Numbers must include units if available.
- No emojis, no opinions, no invented data.
- If a field is missing, return an empty list (or empty strings in overview).
STRICTLY output JSON ONLY.
Prompt version: {DOCUMENT_INTELLIGENCE_VERSION}
"""

MEETING_INTELLIGENCE_PROMPT = f"""
SYSTEM PROMPT:

You are a Meeting Intelligence Extractor.
Your job is to convert noisy meeting transcripts into structured intelligence.
Remove greetings, filler, emotions, emojis. Keep only facts, decisions, action items,
points of disagreement, risks, and participant worldviews.

Return STRICT JSON ONLY with this schema:
{{
  "meeting_overview": {{
    "title": "...",
    "date_hint": "...",
    "summary": "1-3 sentences, factual only"
  }},
  "participants": [
    {{
      "name": "...",
      "role": "...",
      "decision_style": "...",
      "values": ["..."],
      "risk_bias": "risk-averse | balanced | risk-seeking",
      "veto_power": "high | medium | low"
    }}
  ],
  "key_points": ["..."],
  "decisions": ["..."],
  "open_questions": ["..."],
  "conflicts": ["..."],
  "risks": ["..."],
  "action_items": ["..."]
}}

Rules:
- Identify participants explicitly mentioned by name.
- If speaker tags exist, infer role and values.
- Do NOT invent participants not in the transcript.
- Output JSON only.
Prompt version: {MEETING_INTELLIGENCE_VERSION}
"""


def extract_document_intelligence(text: str) -> DocumentIntelligence:
    content = _call_llm(DOCUMENT_INTELLIGENCE_PROMPT, text)
    cleaned = _extract_json_block(content)
    if not cleaned or not cleaned.startswith("{"):
        raise ValueError("Invalid JSON output from LLM")
    return DocumentIntelligence.model_validate_json(cleaned)


def extract_meeting_intelligence(text: str) -> MeetingIntelligence:
    content = _call_llm(MEETING_INTELLIGENCE_PROMPT, text)
    cleaned = _extract_json_block(content)
    if not cleaned or not cleaned.startswith("{"):
        raise ValueError("Invalid JSON output from LLM")
    return MeetingIntelligence.model_validate_json(cleaned)


def _call_llm(system_prompt: str, text: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not configured")
    if OpenAI is not None:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            stream=False
        )
        return response.choices[0].message.content.strip()

    response = requests.post(
        DEEPSEEK_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        },
        timeout=1000
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _extract_json_block(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
