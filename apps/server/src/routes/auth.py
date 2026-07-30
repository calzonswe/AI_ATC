from fastapi import APIRouter, HTTPException
from structlog import get_logger

from ..auth.schemas import LoginRequest, TokenResponse, RefreshRequest
from ..auth.service import jwt_service
from ..settings import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if body.username != settings.auth_admin_username:
        logger.warning("login_failed", username=body.username, reason="unknown_user")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if body.password != settings.auth_admin_password:
        logger.warning("login_failed", username=body.username, reason="wrong_password")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = jwt_service.create_access_token(body.username)
    refresh_token = jwt_service.create_refresh_token(body.username)

    logger.info("login_success", username=body.username)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    payload = jwt_service.validate_refresh_token(body.refresh_token)
    if payload is None:
        logger.warning("refresh_failed", reason="invalid_or_expired")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    subject = payload["sub"]
    access_token = jwt_service.create_access_token(subject)
    refresh_token = jwt_service.create_refresh_token(subject)

    logger.info("refresh_success", username=subject)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
