from base64 import urlsafe_b64encode
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SecretBox:
    def __init__(self, key: str):
        if not key:
            raise ValueError("CREDENTIAL_ENCRYPTION_KEY is required")
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self.fernet = Fernet(urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Invalid encrypted secret") from exc


def mask_secret(value: str) -> str:
    return f"...{value[-4:]}" if value else ""
