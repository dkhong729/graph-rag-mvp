from pydantic import BaseModel
from typing import Any, List, Optional


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    password_confirm: Optional[str] = None
    display_name: Optional[str] = None
    username: Optional[str] = None


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthVerifyRequest(BaseModel):
    token: str


class AuthPasswordRequest(BaseModel):
    email: str


class AuthPasswordResetRequest(BaseModel):
    token: str
    new_password: str
    new_password_confirm: Optional[str] = None


class WorkspaceGenerateRequest(BaseModel):
    text: str
    style: str = "technical"


class MeetingGenerateRequest(BaseModel):
    transcript: str
    style: str = "executive"


class RagAskRequest(BaseModel):
    query: str
    owner_type: str
    owner_id: str
    target: str = "all"
    language: Optional[str] = "en"
    persona: Optional[str] = None


class PageUpdateRequest(BaseModel):
    html: str
    metadata: Optional[Any] = None


class ExtractResult(BaseModel):
    contexts: List[Any]


class DocumentIntelligence(BaseModel):
    document_overview: Any
    key_facts: List[Any]
    key_numbers: List[Any]
    core_results: List[Any]
    assumptions: List[Any]
    dependencies: List[Any]
    uncertainties: List[Any]
    claims_requiring_validation: List[Any]


class MeetingIntelligence(BaseModel):
    meeting_overview: Any
    participants: List[Any]
    key_points: List[Any]
    decisions: List[Any]
    open_questions: List[Any]
    conflicts: List[Any]
    risks: List[Any]
    action_items: List[Any]
