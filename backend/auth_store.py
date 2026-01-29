import secrets
import time
from typing import Dict, Optional

from db import authenticate_user as db_authenticate_user
from db import create_user as db_create_user
from db import get_or_create_user_by_email
from db import mark_email_verified

SESSIONS: Dict[str, Dict[str, str]] = {}
SESSION_TTL_SECONDS = 60 * 60 * 8


def create_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    username: Optional[str] = None
):
    user = db_create_user(
        email=email,
        password=password,
        display_name=display_name,
        username=username
    )
    if not user:
        return None
    token = _create_session(user["user_id"])
    return {"user": user, "token": token}


def authenticate_user(email: str, password: str):
    user = db_authenticate_user(email=email, password=password)
    if not user:
        return None
    if not user.get("email_verified", True):
        # Legacy accounts: allow login and mark verified.
        mark_email_verified(user["user_id"])
    token = _create_session(user["user_id"])
    return {"user": user, "token": token}


def oauth_login(email: str, display_name: Optional[str] = None):
    user = get_or_create_user_by_email(email=email, display_name=display_name)
    token = _create_session(user["user_id"])
    return {"user": user, "token": token}


def _create_session(user_id: str) -> str:
    token = secrets.token_hex(16)
    SESSIONS[token] = {
        "user_id": user_id,
        "expires_at": _now_ts() + SESSION_TTL_SECONDS
    }
    return token


def get_user_from_token(token: str) -> Optional[Dict[str, str]]:
    session = SESSIONS.get(token)
    if not session:
        return None
    if session.get("expires_at", 0) < _now_ts():
        SESSIONS.pop(token, None)
        return None
    return session


def _now_ts() -> int:
    return int(time.time())
