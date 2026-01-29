import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import psycopg2
from psycopg2.extras import Json

from dotenv import load_dotenv
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com"

DB_NAME = os.getenv("PGDATABASE", "")
DB_USER = os.getenv("PGUSER", "")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
DB_HOST = os.getenv("PGHOST", "")
DB_PORT = int(os.getenv("PGPORT", ""))


def _get_conn():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


def _hash_password(password: str, salt: str) -> str:
    payload = f"{salt}:{password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def init_db() -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    display_name TEXT,
                    provider TEXT DEFAULT 'local',
                    email_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'local';")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_idx ON users (username);")
            cur.execute("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    title TEXT,
                    source_type TEXT,
                    source_filename TEXT,
                    raw_text TEXT,
                    encrypted_path TEXT,
                    encryption_method TEXT,
                    decision_contexts JSONB,
                    document_intelligence JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_records (
                    meeting_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    title TEXT,
                    source_filename TEXT,
                    transcript_text TEXT,
                    encrypted_path TEXT,
                    encryption_method TEXT,
                    meeting_intelligence JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS personas (
                    persona_id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL REFERENCES meeting_records(meeting_id),
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    name TEXT NOT NULL,
                    stance_json JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_pages (
                    page_id TEXT PRIMARY KEY,
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    style TEXT NOT NULL,
                    html TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    messages_json JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_intelligence JSONB;"
            )
            cur.execute(
                "ALTER TABLE meeting_records ADD COLUMN IF NOT EXISTS meeting_intelligence JSONB;"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS email_verifications (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    email TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
            )


def ensure_user(
    user_id: str,
    email: str,
    password: str,
    display_name: Optional[str] = None,
    username: Optional[str] = None,
    provider: str = "local",
    email_verified: bool = False
) -> Dict[str, str]:
    salt = secrets.token_hex(8)
    password_hash = _hash_password(password, salt)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, email, username, password_hash, salt, display_name, provider, email_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, email, username, password_hash, salt, display_name or user_id, provider, email_verified)
            )

    return {
        "user_id": user_id,
        "display_name": display_name or user_id
    }


def create_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    username: Optional[str] = None
) -> Optional[Dict[str, str]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return None
            if username:
                cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    return None

    user_id = f"user_{uuid4().hex[:8]}"
    return ensure_user(user_id, email, password, display_name, username=username)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, str]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, display_name, password_hash, salt, email_verified, username
                FROM users WHERE email = %s
                """,
                (email,)
            )
            row = cur.fetchone()
            if not row:
                return None
            user_id, display_name, password_hash, salt, email_verified, username = row
            if _hash_password(password, salt) != password_hash:
                return None
            return {
                "user_id": user_id,
                "display_name": display_name or user_id,
                "email_verified": bool(email_verified),
                "username": username
            }


def get_or_create_user_by_email(
    email: str,
    display_name: Optional[str] = None
) -> Dict[str, str]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, display_name FROM users WHERE email = %s",
                (email,)
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE users SET email_verified = TRUE, provider = 'google' WHERE email = %s",
                    (email,)
                )
                return {
                    "user_id": row[0],
                    "display_name": row[1] or row[0]
                }

    temp_password = secrets.token_hex(12)
    username = email.split("@")[0]
    return ensure_user(
        user_id=f"user_{uuid4().hex[:8]}",
        email=email,
        password=temp_password,
        display_name=display_name or email.split("@")[0],
        username=username,
        provider="google",
        email_verified=True
    )


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, display_name, email_verified, username
                FROM users WHERE email = %s
                """,
                (email,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "display_name": row[1] or row[0],
                "email_verified": bool(row[2]),
                "username": row[3]
            }


def get_or_create_project(user_id: str, name: str = "default") -> str:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id FROM projects
                WHERE user_id = %s AND name = %s
                """,
                (user_id, name)
            )
            row = cur.fetchone()
            if row:
                return row[0]
            project_id = f"proj_{uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO projects (project_id, user_id, name)
                VALUES (%s, %s, %s)
                """,
                (project_id, user_id, name)
            )
            return project_id


def create_document(
    user_id: str,
    project_id: str,
    title: str,
    source_type: str,
    source_filename: Optional[str],
    raw_text: Optional[str],
    encrypted_path: str,
    encryption_method: str
) -> str:
    document_id = f"doc_{uuid4().hex[:8]}"
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (
                    document_id, project_id, user_id, title, source_type,
                    source_filename, raw_text, encrypted_path, encryption_method
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    document_id,
                    project_id,
                    user_id,
                    title,
                    source_type,
                    source_filename,
                    raw_text,
                    encrypted_path,
                    encryption_method
                )
            )
    return document_id


def update_document_contexts(
    user_id: str,
    document_id: str,
    decision_contexts: List[Dict[str, Any]]
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET decision_contexts = %s,
                    updated_at = NOW()
                WHERE user_id = %s AND document_id = %s
                """,
                (Json(decision_contexts), user_id, document_id)
            )


def update_document_intelligence(
    user_id: str,
    document_id: str,
    document_intelligence: Dict[str, Any]
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET document_intelligence = %s,
                    updated_at = NOW()
                WHERE user_id = %s AND document_id = %s
                """,
                (Json(document_intelligence), user_id, document_id)
            )


def list_documents(user_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, title, source_type, source_filename,
                       document_intelligence, created_at, updated_at
                FROM documents WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            return [
                {
                    "document_id": row[0],
                    "title": row[1],
                    "source_type": row[2],
                    "source_filename": row[3],
                    "has_intelligence": bool(row[4]),
                    "created_at": row[5].isoformat() if row[5] else None,
                    "updated_at": row[6].isoformat() if row[6] else None
                }
                for row in cur.fetchall()
            ]


def get_document(user_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, title, source_type, source_filename,
                       raw_text, decision_contexts, document_intelligence, created_at, updated_at
                FROM documents
                WHERE user_id = %s AND document_id = %s
                """,
                (user_id, document_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "document_id": row[0],
                "title": row[1],
                "source_type": row[2],
                "source_filename": row[3],
                "raw_text": row[4],
                "decision_contexts": row[5] or [],
                "document_intelligence": row[6] or {},
                "created_at": row[7].isoformat() if row[7] else None,
                "updated_at": row[8].isoformat() if row[8] else None
            }


def create_meeting_record(
    user_id: str,
    project_id: str,
    title: str,
    source_filename: Optional[str],
    transcript_text: Optional[str],
    encrypted_path: str,
    encryption_method: str
) -> str:
    meeting_id = f"meet_{uuid4().hex[:8]}"
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meeting_records (
                    meeting_id, project_id, user_id, title, source_filename,
                    transcript_text, encrypted_path, encryption_method
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    meeting_id,
                    project_id,
                    user_id,
                    title,
                    source_filename,
                    transcript_text,
                    encrypted_path,
                    encryption_method
                )
            )
    return meeting_id


def update_meeting_transcript(
    user_id: str,
    meeting_id: str,
    transcript_text: str
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE meeting_records
                SET transcript_text = %s, updated_at = NOW()
                WHERE user_id = %s AND meeting_id = %s
                """,
                (transcript_text, user_id, meeting_id)
            )


def update_meeting_file(
    user_id: str,
    meeting_id: str,
    source_filename: Optional[str],
    encrypted_path: str,
    encryption_method: str
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE meeting_records
                SET source_filename = %s,
                    encrypted_path = %s,
                    encryption_method = %s,
                    updated_at = NOW()
                WHERE user_id = %s AND meeting_id = %s
                """,
                (source_filename, encrypted_path, encryption_method, user_id, meeting_id)
            )


def update_meeting_intelligence(
    user_id: str,
    meeting_id: str,
    meeting_intelligence: Dict[str, Any]
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE meeting_records
                SET meeting_intelligence = %s, updated_at = NOW()
                WHERE user_id = %s AND meeting_id = %s
                """,
                (Json(meeting_intelligence), user_id, meeting_id)
            )


def list_meetings(user_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT meeting_id, title, source_filename, meeting_intelligence, created_at, updated_at
                FROM meeting_records WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            return [
                {
                    "meeting_id": row[0],
                    "title": row[1],
                    "source_filename": row[2],
                    "has_intelligence": bool(row[3]),
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None
                }
                for row in cur.fetchall()
            ]


def get_meeting(user_id: str, meeting_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT meeting_id, title, source_filename, transcript_text,
                       meeting_intelligence, created_at, updated_at
                FROM meeting_records WHERE user_id = %s AND meeting_id = %s
                """,
                (user_id, meeting_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "meeting_id": row[0],
                "title": row[1],
                "source_filename": row[2],
                "transcript_text": row[3],
                "meeting_intelligence": row[4] or {},
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None
            }


def replace_personas(
    user_id: str,
    meeting_id: str,
    personas: List[Dict[str, Any]]
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM personas WHERE user_id = %s AND meeting_id = %s",
                (user_id, meeting_id)
            )
            for persona in personas:
                persona_id = persona.get("persona_id") or f"per_{uuid4().hex[:8]}"
                cur.execute(
                    """
                    INSERT INTO personas (
                        persona_id, meeting_id, user_id, name, stance_json
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        persona_id,
                        meeting_id,
                        user_id,
                        persona.get("name", "Unknown"),
                        Json(persona)
                    )
                )


def list_personas(user_id: str, meeting_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT persona_id, name, stance_json
                FROM personas WHERE user_id = %s AND meeting_id = %s
                ORDER BY created_at ASC
                """,
                (user_id, meeting_id)
            )
            return [
                {
                    "persona_id": row[0],
                    "name": row[1],
                    "stance": row[2] or {}
                }
                for row in cur.fetchall()
            ]


def create_generated_page(
    user_id: str,
    owner_type: str,
    owner_id: str,
    style: str,
    html: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    page_id = f"page_{uuid4().hex[:8]}"
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO generated_pages (
                    page_id, owner_type, owner_id, user_id, style, html, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (page_id, owner_type, owner_id, user_id, style, html, Json(metadata or {}))
            )
    return page_id


def update_generated_page(
    user_id: str,
    page_id: str,
    html: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE generated_pages
                SET html = %s,
                    metadata = %s,
                    updated_at = NOW()
                WHERE user_id = %s AND page_id = %s
                """,
                (html, Json(metadata or {}), user_id, page_id)
            )


def list_generated_pages(
    user_id: str,
    owner_type: str,
    owner_id: str
) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id, style, created_at, updated_at
                FROM generated_pages
                WHERE user_id = %s AND owner_type = %s AND owner_id = %s
                ORDER BY created_at DESC
                """,
                (user_id, owner_type, owner_id)
            )
            return [
                {
                    "page_id": row[0],
                    "style": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None
                }
                for row in cur.fetchall()
            ]


def get_generated_page(user_id: str, page_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id, owner_type, owner_id, style, html, metadata, created_at, updated_at
                FROM generated_pages
                WHERE user_id = %s AND page_id = %s
                """,
                (user_id, page_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "page_id": row[0],
                "owner_type": row[1],
                "owner_id": row[2],
                "style": row[3],
                "html": row[4],
                "metadata": row[5] or {},
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None
            }


def delete_generated_page(user_id: str, page_id: str) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM generated_pages WHERE user_id = %s AND page_id = %s",
                (user_id, page_id)
            )


def delete_document(user_id: str, document_id: str) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM generated_pages WHERE user_id = %s AND owner_type = %s AND owner_id = %s",
                (user_id, "document", document_id)
            )
            cur.execute(
                "DELETE FROM conversations WHERE user_id = %s AND owner_type = %s AND owner_id = %s",
                (user_id, "document", document_id)
            )
            cur.execute(
                "DELETE FROM documents WHERE user_id = %s AND document_id = %s",
                (user_id, document_id)
            )


def upsert_conversation(
    user_id: str,
    owner_type: str,
    owner_id: str,
    messages: List[Dict[str, Any]]
) -> str:
    conversation_id = f"conv_{uuid4().hex[:8]}"
    now = datetime.utcnow()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    conversation_id, owner_type, owner_id, user_id, messages_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (conversation_id, owner_type, owner_id, user_id, Json(messages), now, now)
            )
    return conversation_id


def list_conversations(user_id: str, owner_type: str, owner_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id, messages_json, created_at, updated_at
                FROM conversations
                WHERE user_id = %s AND owner_type = %s AND owner_id = %s
                ORDER BY created_at DESC
                """,
                (user_id, owner_type, owner_id)
            )
            return [
                {
                    "conversation_id": row[0],
                    "messages": row[1] or [],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None
                }
                for row in cur.fetchall()
            ]


def create_email_verification(user_id: str, email: str, ttl_hours: int = 24) -> str:
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_verifications (token, user_id, email, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (token, user_id, email, expires_at)
            )
    return token


def verify_email_token(token: str) -> Optional[str]:
    now = datetime.utcnow()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id FROM email_verifications
                WHERE token = %s AND expires_at > %s
                """,
                (token, now)
            )
            row = cur.fetchone()
            if not row:
                return None
            user_id = row[0]
            cur.execute(
                "UPDATE users SET email_verified = TRUE WHERE user_id = %s",
                (user_id,)
            )
            cur.execute("DELETE FROM email_verifications WHERE token = %s", (token,))
            return user_id


def create_password_reset(email: str, ttl_hours: int = 2) -> Optional[str]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return None
            user_id = row[0]
            token = secrets.token_urlsafe(16)
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            cur.execute(
                """
                INSERT INTO password_resets (token, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (token, user_id, expires_at)
            )
            return token


def reset_password(token: str, new_password: str) -> bool:
    now = datetime.utcnow()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id FROM password_resets
                WHERE token = %s AND expires_at > %s
                """,
                (token, now)
            )
            row = cur.fetchone()
            if not row:
                return False
            user_id = row[0]
            salt = secrets.token_hex(8)
            password_hash = _hash_password(new_password, salt)
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s, salt = %s, updated_at = NOW()
                WHERE user_id = %s
                """,
                (password_hash, salt, user_id)
            )
            cur.execute("DELETE FROM password_resets WHERE token = %s", (token,))
            return True


def mark_email_verified(user_id: str) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET email_verified = TRUE, updated_at = NOW() WHERE user_id = %s",
                (user_id,)
            )
