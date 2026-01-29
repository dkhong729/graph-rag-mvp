import os
from typing import Tuple

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None


def _get_fernet() -> "Fernet":
    if Fernet is None:
        raise RuntimeError("cryptography is required for file encryption.")
    key = os.getenv("FILE_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("FILE_ENCRYPTION_KEY is not configured.")
    return Fernet(key)


def encrypt_bytes(payload: bytes) -> Tuple[bytes, str]:
    fernet = _get_fernet()
    return fernet.encrypt(payload), "fernet"
