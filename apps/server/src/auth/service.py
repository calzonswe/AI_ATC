from typing import Optional
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from ..settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTService:
    def __init__(self):
        self.secret = settings.auth_jwt_secret
        self.algorithm = settings.auth_jwt_algorithm
        self.access_expire = timedelta(minutes=settings.auth_access_token_expire_minutes)
        self.refresh_expire = timedelta(days=settings.auth_refresh_token_expire_days)

    def create_access_token(self, subject: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "exp": now + self.access_expire,
            "iat": now,
            "jti": uuid.uuid4().hex,
            "type": "access",
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, subject: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "exp": now + self.refresh_expire,
            "iat": now,
            "jti": uuid.uuid4().hex,
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def validate_access_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.PyJWTError:
            return None

    def validate_refresh_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            if payload.get("type") != "refresh":
                return None
            return payload
        except jwt.PyJWTError:
            return None

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def hash_password(self, plain: str) -> str:
        return pwd_context.hash(plain)


jwt_service = JWTService()
