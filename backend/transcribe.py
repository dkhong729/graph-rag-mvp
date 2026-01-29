import os
import tempfile
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def transcribe_audio(
    content: bytes,
    filename: str,
    language: Optional[str] = None
) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is required for transcription")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_AUDIO_MODEL", "whisper-1")
    client = OpenAI(api_key=api_key, base_url=base_url or None)

    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language
            )
        return getattr(response, "text", "") or ""
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
