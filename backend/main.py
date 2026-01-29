import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

sys.path.append(str(Path(__file__).resolve().parent))
from auth_store import authenticate_user, create_user, get_user_from_token, oauth_login
from crypto_utils import encrypt_bytes
from db import (
    create_document,
    create_generated_page,
    create_meeting_record,
    delete_document,
    delete_generated_page,
    get_document,
    get_generated_page,
    get_meeting,
    get_or_create_project,
    get_user_by_email,
    init_db,
    list_documents,
    list_generated_pages,
    list_meetings,
    list_personas,
    replace_personas,
    create_email_verification,
    verify_email_token,
    create_password_reset,
    reset_password,
    upsert_conversation,
    update_document_intelligence,
    update_generated_page,
    update_meeting_intelligence,
    update_meeting_transcript,
    update_meeting_file
)
from extractor import extract_document_intelligence, extract_meeting_intelligence
from pipelines import build_document_render_chain, build_meeting_chain, extract_personas_from_transcript
from prompt_versions import (
    DOCUMENT_INTELLIGENCE_VERSION,
    MEETING_INTELLIGENCE_VERSION,
    DOCUMENT_RENDER_VERSION,
    MEETING_RENDER_VERSION,
    PERSONA_EXTRACT_VERSION
)
from rag import build_rag_chain, select_contexts
from transcribe import transcribe_audio
from schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthVerifyRequest,
    AuthPasswordRequest,
    AuthPasswordResetRequest,
    PageUpdateRequest,
    RagAskRequest
)

app = FastAPI()

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]
env_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
extra_origins = [item.strip() for item in env_origins.split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins + extra_origins,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
def _bootstrap() -> None:
    init_db()


def _require_user(authorization: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user = get_user_from_token(token)
        if user:
            return user["user_id"]
    raise HTTPException(status_code=401, detail="Login required")


def _read_file_text(file: UploadFile, content: bytes) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".pdf":
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
            return text
    if suffix == ".docx":
        try:
            import docx2txt
        except ImportError:
            raise HTTPException(status_code=503, detail="docx2txt not installed")
        return docx2txt.process(io.BytesIO(content))
    if suffix in [".txt", ".md"]:
        return content.decode("utf-8", errors="ignore")
    return content.decode("utf-8", errors="ignore")


def _store_encrypted_file(content: bytes, suffix: str) -> Dict[str, str]:
    uploads_dir = Path(__file__).resolve().parent / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    encrypted_payload, encryption_method = encrypt_bytes(content)
    encrypted_name = f"{os.urandom(8).hex()}{suffix}.bin"
    encrypted_path = uploads_dir / encrypted_name
    encrypted_path.write_bytes(encrypted_payload)
    return {
        "encrypted_path": str(encrypted_path),
        "encryption_method": encryption_method
    }


def _sse_event(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _render_pdf_from_html(html: str) -> bytes:
    try:
        dll_path = os.getenv("WEASYPRINT_DLL_PATH")
        if dll_path and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_path)
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        raise
    except OSError:
        raise
    except Exception:
        raise


@app.post("/api/auth/register")
def register(payload: AuthRegisterRequest):
    if payload.password_confirm and payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Password confirmation does not match")
    user = create_user(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        username=payload.username
    )
    if not user:
        raise HTTPException(status_code=409, detail="User already exists")
    token = create_email_verification(user["user"]["user_id"], payload.email)
    response = {
        "user": user["user"],
        "token": user["token"],
        "verification_required": True
    }
    if os.getenv("EMAIL_VERIFICATION_EXPOSE_TOKEN", "true").lower() == "true":
        response["verification_token"] = token
    return response


@app.post("/api/auth/login")
def login(payload: AuthLoginRequest):
    user = authenticate_user(email=payload.email, password=payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("error") == "email_not_verified":
        raise HTTPException(status_code=403, detail="Email not verified")
    return user


@app.post("/api/auth/oauth")
def oauth(payload: AuthRegisterRequest):
    user = oauth_login(email=payload.email, display_name=payload.display_name)
    return user


@app.post("/api/auth/verify")
def verify_email(payload: AuthVerifyRequest):
    user_id = verify_email_token(payload.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return {"status": "verified"}


@app.post("/api/auth/verify/request")
def request_verification(payload: AuthPasswordRequest):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_email_verification(user["user_id"], payload.email)
    response = {"status": "sent"}
    if os.getenv("EMAIL_VERIFICATION_EXPOSE_TOKEN", "true").lower() == "true":
        response["verification_token"] = token
    return response


@app.post("/api/auth/password/request")
def request_password_reset(payload: AuthPasswordRequest):
    token = create_password_reset(payload.email)
    if not token:
        raise HTTPException(status_code=404, detail="User not found")
    response = {"status": "sent"}
    if os.getenv("PASSWORD_RESET_EXPOSE_TOKEN", "true").lower() == "true":
        response["reset_token"] = token
    return response


@app.post("/api/auth/password/reset")
def password_reset(payload: AuthPasswordResetRequest):
    if payload.new_password_confirm and payload.new_password != payload.new_password_confirm:
        raise HTTPException(status_code=400, detail="Password confirmation does not match")
    ok = reset_password(payload.token, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return {"status": "reset"}


@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(default=None)):
    user_id = _require_user(authorization)
    return {"user_id": user_id}


@app.get("/api/documents")
def get_documents(authorization: Optional[str] = Header(default=None)):
    user_id = _require_user(authorization)
    return {"documents": list_documents(user_id)}


@app.post("/api/documents/delete")
def delete_documents(
    payload: Dict[str, List[str]],
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    ids = payload.get("document_ids", [])
    for doc_id in ids:
        delete_document(user_id, doc_id)
    return {"status": "deleted", "count": len(ids)}


@app.post("/api/documents")
async def create_document_api(
    file: UploadFile = File(None),
    text: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    project_id = get_or_create_project(user_id)

    if not file and not text:
        raise HTTPException(status_code=400, detail="File or text required")

    source_type = "text" if text else "file"
    source_filename = file.filename if file else None
    raw_text = text or ""
    encrypted_path = ""
    encryption_method = ""

    if file:
        content = await file.read()
        raw_text = _read_file_text(file, content)
        suffix = Path(file.filename or "").suffix.lower()
        stored = _store_encrypted_file(content, suffix)
        encrypted_path = stored["encrypted_path"]
        encryption_method = stored["encryption_method"]

    document_id = create_document(
        user_id=user_id,
        project_id=project_id,
        title=title or (Path(source_filename).stem if source_filename else "Untitled"),
        source_type=source_type,
        source_filename=source_filename,
        raw_text=raw_text,
        encrypted_path=encrypted_path,
        encryption_method=encryption_method
    )

    return {"document_id": document_id}


@app.get("/api/documents/{document_id}")
def get_document_api(
    document_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    document = get_document(user_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.get("/api/documents/{document_id}/intelligence")
def get_document_intelligence_api(
    document_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    document = get_document(user_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    pages = list_generated_pages(user_id, "document", document_id)
    previous = None
    if len(pages) >= 2:
        previous_page = get_generated_page(user_id, pages[1]["page_id"])
        if previous_page:
            previous = previous_page.get("metadata", {}).get("document_intelligence")
    return {
        "document_id": document_id,
        "current": document.get("document_intelligence") or {},
        "previous": previous
    }


@app.post("/api/documents/{document_id}/generate")
def generate_document_page(
    document_id: str,
    style: str = Form("technical"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    document = get_document(user_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    def stream():
        raw_text = document.get("raw_text") or ""
        yield _sse_event("progress", {
            "stage": "Parsing",
            "percent": 10,
            "message": "Parsing source content"
        })
        doc_intelligence = document.get("document_intelligence") or {}
        if not doc_intelligence:
            try:
                yield _sse_event("progress", {
                    "stage": "Decision Structuring",
                    "percent": 30,
                    "message": "Extracting document intelligence"
                })
                result = extract_document_intelligence(raw_text)
                doc_intelligence = result.model_dump()
                doc_intelligence["_meta"] = {
                    "extractor_version": DOCUMENT_INTELLIGENCE_VERSION
                }
                update_document_intelligence(user_id, document_id, doc_intelligence)
            except Exception as exc:
                yield _sse_event("error", {"message": f"Extraction failed: {exc}"})
        elif "_meta" not in doc_intelligence:
            doc_intelligence["_meta"] = {
                "extractor_version": DOCUMENT_INTELLIGENCE_VERSION,
                "source": "cached"
            }
        yield _sse_event("progress", {
            "stage": "Decision Structuring",
            "percent": 55,
            "message": "Structuring document intelligence"
        })

        chain = build_document_render_chain()
        rendered_len = 0
        for chunk in chain.stream({
            "doc_intelligence": doc_intelligence,
            "style": style,
            "language": language,
            "page_limit": page_limit
        }):
            rendered_len += len(chunk)
            percent = min(90, 60 + int(rendered_len / 80))
            yield _sse_event("progress", {
                "stage": "HTML Rendering",
                "percent": percent,
                "message": "Rendering decision page"
            })
            yield _sse_event("html", {"chunk": chunk})

        yield _sse_event("progress", {
            "stage": "Finalizing",
            "percent": 100,
            "message": "Ready"
        })
        yield _sse_event("done", {"status": "ok"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/documents/{document_id}/render")
def render_document_page(
    document_id: str,
    style: str = Form("technical"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    document = get_document(user_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_intelligence = document.get("document_intelligence") or {}
    if not doc_intelligence:
        raise HTTPException(status_code=400, detail="No document intelligence available")

    chain = build_document_render_chain()

    def stream():
        yield _sse_event("progress", {
            "stage": "HTML Rendering",
            "percent": 60,
            "message": "Rendering decision page"
        })
        rendered_len = 0
        for chunk in chain.stream({
            "doc_intelligence": doc_intelligence,
            "style": style,
            "language": language,
            "page_limit": page_limit
        }):
            rendered_len += len(chunk)
            percent = min(95, 60 + int(rendered_len / 100))
            yield _sse_event("progress", {
                "stage": "HTML Rendering",
                "percent": percent,
                "message": "Rendering decision page"
            })
            yield _sse_event("html", {"chunk": chunk})
        yield _sse_event("progress", {
            "stage": "Finalizing",
            "percent": 100,
            "message": "Ready"
        })
        yield _sse_event("done", {"status": "ok"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/documents/{document_id}/finalize")
def finalize_document_page(
    document_id: str,
    html: str = Form(...),
    style: str = Form("technical"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    document = get_document(user_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_intelligence = document.get("document_intelligence") or {}
    if not doc_intelligence:
        result = extract_document_intelligence(document.get("raw_text") or "")
        doc_intelligence = result.model_dump()
        doc_intelligence["_meta"] = {
            "extractor_version": DOCUMENT_INTELLIGENCE_VERSION
        }
        update_document_intelligence(user_id, document_id, doc_intelligence)
    elif "_meta" not in doc_intelligence:
        doc_intelligence["_meta"] = {
            "extractor_version": DOCUMENT_INTELLIGENCE_VERSION,
            "source": "cached"
        }
    page_id = create_generated_page(
        user_id=user_id,
        owner_type="document",
        owner_id=document_id,
        style=style,
        html=html,
        metadata={
            "document_intelligence": doc_intelligence,
            "language": language,
            "page_limit": page_limit,
            "renderer_version": DOCUMENT_RENDER_VERSION,
            "extractor_version": DOCUMENT_INTELLIGENCE_VERSION
        }
    )
    return {"page_id": page_id}


@app.get("/api/documents/{document_id}/pages")
def list_document_pages(
    document_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    return {"pages": list_generated_pages(user_id, "document", document_id)}


@app.post("/api/meetings")
async def create_meeting(
    file: UploadFile = File(None),
    transcript: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    project_id = get_or_create_project(user_id)

    if not file and not transcript:
        raise HTTPException(status_code=400, detail="Audio file or transcript required")

    source_filename = file.filename if file else None
    transcript_text = transcript or ""
    encrypted_path = ""
    encryption_method = ""

    if file:
        content = await file.read()
        suffix = Path(file.filename or "").suffix.lower()
        stored = _store_encrypted_file(content, suffix)
        encrypted_path = stored["encrypted_path"]
        encryption_method = stored["encryption_method"]
    meeting_id = create_meeting_record(
        user_id=user_id,
        project_id=project_id,
        title=title or Path(source_filename or "Meeting").stem,
        source_filename=source_filename,
        transcript_text=transcript_text,
        encrypted_path=encrypted_path,
        encryption_method=encryption_method
    )
    return {"meeting_id": meeting_id}


@app.post("/api/meetings/{meeting_id}/transcript")
def update_transcript(
    meeting_id: str,
    transcript: str = Form(...),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    update_meeting_transcript(user_id, meeting_id, transcript)
    return {"status": "ok"}


@app.post("/api/meetings/{meeting_id}/audio")
async def transcribe_meeting_audio(
    meeting_id: str,
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    content = await file.read()
    suffix = Path(file.filename or "").suffix.lower()
    stored = _store_encrypted_file(content, suffix)
    update_meeting_file(
        user_id,
        meeting_id,
        file.filename,
        stored["encrypted_path"],
        stored["encryption_method"]
    )
    try:
        transcript = transcribe_audio(content, file.filename or "audio", language)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Transcription failed: {exc}")
    update_meeting_transcript(user_id, meeting_id, transcript)
    return {"transcript": transcript}


@app.get("/api/meetings")
def get_meetings(authorization: Optional[str] = Header(default=None)):
    user_id = _require_user(authorization)
    return {"meetings": list_meetings(user_id)}


@app.get("/api/meetings/{meeting_id}")
def get_meeting_api(
    meeting_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting["personas"] = list_personas(user_id, meeting_id)
    return meeting


@app.get("/api/meetings/{meeting_id}/pages")
def list_meeting_pages(
    meeting_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    return {"pages": list_generated_pages(user_id, "meeting", meeting_id)}


@app.post("/api/meetings/{meeting_id}/generate")
def generate_meeting_page(
    meeting_id: str,
    style: str = Form("executive"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    def stream():
        transcript = meeting.get("transcript_text") or ""
        yield _sse_event("progress", {
            "stage": "Parsing",
            "percent": 20,
            "message": "Parsing transcript"
        })
        meeting_intelligence = meeting.get("meeting_intelligence") or {}
        if not meeting_intelligence:
            try:
                yield _sse_event("progress", {
                    "stage": "Decision Structuring",
                    "percent": 40,
                    "message": "Extracting meeting intelligence"
                })
                result = extract_meeting_intelligence(transcript)
                meeting_intelligence = result.model_dump()
                meeting_intelligence["_meta"] = {
                    "extractor_version": MEETING_INTELLIGENCE_VERSION
                }
                update_meeting_intelligence(user_id, meeting_id, meeting_intelligence)
                participants = meeting_intelligence.get("participants") or []
                if participants:
                    replace_personas(user_id, meeting_id, participants)
            except Exception as exc:
                yield _sse_event("error", {"message": f"Extraction failed: {exc}"})
        elif "_meta" not in meeting_intelligence:
            meeting_intelligence["_meta"] = {
                "extractor_version": MEETING_INTELLIGENCE_VERSION,
                "source": "cached"
            }
        chain = build_meeting_chain()
        rendered_len = 0
        for chunk in chain.stream({
            "meeting_intelligence": meeting_intelligence,
            "style": style,
            "language": language,
            "page_limit": page_limit
        }):
            rendered_len += len(chunk)
            percent = min(90, 30 + int(rendered_len / 80))
            yield _sse_event("progress", {
                "stage": "HTML Rendering",
                "percent": percent,
                "message": "Rendering meeting page"
            })
            yield _sse_event("html", {"chunk": chunk})
        yield _sse_event("progress", {
            "stage": "Finalizing",
            "percent": 100,
            "message": "Ready"
        })
        yield _sse_event("done", {"status": "ok"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/meetings/{meeting_id}/render")
def render_meeting_page(
    meeting_id: str,
    style: str = Form("executive"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting_intelligence = meeting.get("meeting_intelligence") or {}
    if not meeting_intelligence:
        raise HTTPException(status_code=400, detail="No meeting intelligence available")
    chain = build_meeting_chain()

    def stream():
        payload = {
            "meeting_intelligence": meeting_intelligence,
            "style": style,
            "language": language,
            "page_limit": page_limit
        }
        yield _sse_event("progress", {
            "stage": "HTML Rendering",
            "percent": 60,
            "message": "Rendering meeting page"
        })
        rendered_len = 0
        for chunk in chain.stream(payload):
            rendered_len += len(chunk)
            percent = min(95, 60 + int(rendered_len / 100))
            yield _sse_event("progress", {
                "stage": "HTML Rendering",
                "percent": percent,
                "message": "Rendering meeting page"
            })
            yield _sse_event("html", {"chunk": chunk})
        yield _sse_event("progress", {
            "stage": "Finalizing",
            "percent": 100,
            "message": "Ready"
        })
        yield _sse_event("done", {"status": "ok"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/meetings/{meeting_id}/finalize")
def finalize_meeting_page(
    meeting_id: str,
    html: str = Form(...),
    style: str = Form("executive"),
    language: str = Form("en"),
    page_limit: int = Form(2),
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    meeting = get_meeting(user_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    personas = extract_personas_from_transcript(meeting.get("transcript_text") or "")
    if personas:
        replace_personas(user_id, meeting_id, personas)
    meeting_intelligence = meeting.get("meeting_intelligence") or {}
    if not meeting_intelligence:
        result = extract_meeting_intelligence(meeting.get("transcript_text") or "")
        meeting_intelligence = result.model_dump()
        meeting_intelligence["_meta"] = {
            "extractor_version": MEETING_INTELLIGENCE_VERSION
        }
        update_meeting_intelligence(user_id, meeting_id, meeting_intelligence)
    elif "_meta" not in meeting_intelligence:
        meeting_intelligence["_meta"] = {
            "extractor_version": MEETING_INTELLIGENCE_VERSION,
            "source": "cached"
        }

    page_id = create_generated_page(
        user_id=user_id,
        owner_type="meeting",
        owner_id=meeting_id,
        style=style,
        html=html,
        metadata={
            "personas": personas,
            "meeting_intelligence": meeting_intelligence,
            "language": language,
            "page_limit": page_limit,
            "renderer_version": MEETING_RENDER_VERSION,
            "extractor_version": MEETING_INTELLIGENCE_VERSION,
            "persona_version": PERSONA_EXTRACT_VERSION
        }
    )
    return {"page_id": page_id}


@app.get("/api/pages/{page_id}")
def get_page(page_id: str, authorization: Optional[str] = Header(default=None)):
    user_id = _require_user(authorization)
    page = get_generated_page(user_id, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@app.put("/api/pages/{page_id}")
def update_page(
    page_id: str,
    payload: PageUpdateRequest,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    update_generated_page(user_id, page_id, payload.html, payload.metadata)
    return {"status": "ok"}


@app.delete("/api/pages/{page_id}")
def delete_page(
    page_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    delete_generated_page(user_id, page_id)
    return {"status": "deleted"}


@app.get("/api/pages/{page_id}/pdf")
def download_page_pdf(
    page_id: str,
    authorization: Optional[str] = Header(default=None)
):
    user_id = _require_user(authorization)
    page = get_generated_page(user_id, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    try:
        pdf_bytes = _render_pdf_from_html(page["html"])
    except (ImportError, OSError, Exception):
        pdf_bytes = b""

    if not pdf_bytes:
        cli_path = os.getenv("WEASYPRINT_COMMAND")
        if not cli_path:
            raise HTTPException(status_code=503, detail="PDF renderer not installed")
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / "page.html"
            pdf_path = Path(tmp_dir) / "page.pdf"
            html_path.write_text(page["html"], encoding="utf-8")
            try:
                subprocess.run(
                    [cli_path, str(html_path), str(pdf_path)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"PDF renderer failed: {exc.stderr.decode('utf-8', errors='ignore')}"
                )
            pdf_bytes = pdf_path.read_bytes()
    headers = {
        "Content-Disposition": f"attachment; filename=decision-page-{page_id}.pdf"
    }
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@app.post("/api/rag/ask")
def rag_ask(payload: RagAskRequest, authorization: Optional[str] = Header(default=None)):
    user_id = _require_user(authorization)

    def retriever(params: Dict[str, Any]):
        owner_type = params.get("owner_type")
        owner_id = params.get("owner_id")
        if owner_type == "document":
            document = get_document(user_id, owner_id)
            doc_intelligence = document.get("document_intelligence") if document else {}
            contexts = []
            if doc_intelligence:
                contexts = [
                    {
                        "context_id": owner_id,
                        "conditions": doc_intelligence.get("key_facts", []),
                        "observed_issues": doc_intelligence.get("uncertainties", []),
                        "outcomes": doc_intelligence.get("core_results", []),
                        "decision_boundaries": [
                            {"description": item} for item in doc_intelligence.get("claims_requiring_validation", [])
                        ]
                    }
                ]
        else:
            meeting = get_meeting(user_id, owner_id)
            contexts = list_personas(user_id, owner_id) if meeting else []
            target = params.get("target")
            if target and target != "all":
                contexts = [ctx for ctx in contexts if ctx.get("name") == target]
        return select_contexts(params["query"], contexts or [], limit=5)

    chain = build_rag_chain(retriever)
    answer = chain.invoke({
        "query": payload.query,
        "owner_type": payload.owner_type,
        "owner_id": payload.owner_id,
        "target": payload.target,
        "language": payload.language or "en"
    })

    upsert_conversation(
        user_id=user_id,
        owner_type=payload.owner_type,
        owner_id=payload.owner_id,
        messages=[
            {"role": "user", "content": payload.query},
            {"role": "assistant", "content": answer}
        ]
    )

    return {"answer": answer}
