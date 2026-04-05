import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.models.app_setting import AppSetting
from app.schemas.auth import LoginRequest, ProfileUpdate, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.core.config import settings as app_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import or_
    result = await db.execute(select(User).where(or_(User.username == body.username, User.email == body.username)))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    email_confirmation_sent = False

    # Password change requires current password
    if body.new_password:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not verify_password(body.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.password_hash = hash_password(body.new_password)

    # Check uniqueness for username changes
    if body.username and body.username != current_user.username:
        existing = await db.execute(select(User).where(User.username == body.username, User.id != current_user.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already taken")
        current_user.username = body.username

    # Email change: send confirmation to new email, don't update immediately
    if body.email and body.email != current_user.email:
        existing = await db.execute(select(User).where(User.email == body.email, User.id != current_user.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already taken")
        # Create token with new email embedded
        token = create_access_token(str(current_user.id), f"email_change:{body.email}")
        smtp_settings = await _get_platform_smtp(db)
        sent = _send_email_change_confirmation(smtp_settings, body.email, current_user.full_name or current_user.username, token)
        email_confirmation_sent = sent

    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.company_name is not None:
        current_user.company_name = body.company_name
    if body.phone is not None:
        current_user.phone = body.phone

    await db.flush()
    await db.refresh(current_user)

    result = UserResponse.model_validate(current_user).model_dump()
    if email_confirmation_sent:
        result["email_change_pending"] = body.email
        result["message"] = f"A confirmation email has been sent to {body.email}. Please check your inbox to confirm the change."
    return result


async def _get_platform_smtp(db: AsyncSession) -> dict:
    """Get the platform-level SMTP settings (owner_id IS NULL = super admin's settings)."""
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key.in_(["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from", "smtp_from_name"]),
            AppSetting.owner_id.is_(None),
        )
    )
    settings = {s.key: s.value for s in result.scalars().all()}
    if not settings:
        # Fallback: get super_admin's settings
        sa_result = await db.execute(select(User).where(User.role == UserRole.super_admin).limit(1))
        sa = sa_result.scalar_one_or_none()
        if sa:
            result2 = await db.execute(
                select(AppSetting).where(
                    AppSetting.key.in_(["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from", "smtp_from_name"]),
                    AppSetting.owner_id == sa.id,
                )
            )
            settings = {s.key: s.value for s in result2.scalars().all()}
    return settings


def _send_confirmation_email(smtp_settings: dict, to_email: str, full_name: str, token: str):
    """Send email confirmation link."""
    host = smtp_settings.get("smtp_host", "")
    port = int(smtp_settings.get("smtp_port", 587))
    user = smtp_settings.get("smtp_user", "")
    password = smtp_settings.get("smtp_password", "")
    from_addr = smtp_settings.get("smtp_from", user)
    from_name = smtp_settings.get("smtp_from_name", "NetLedger")

    if not host or not user:
        logger.warning("SMTP not configured, skipping confirmation email")
        return False

    confirm_url = f"https://netl.2max.tech/login?verify={token}"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email
    msg["Subject"] = "Confirm your NetLedger registration"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
        <div style="text-align:center;margin-bottom:20px;">
            <h2 style="color:#e8700a;">NetLedger</h2>
        </div>
        <p>Hi {full_name},</p>
        <p>Thank you for registering on NetLedger. Please confirm your email address by clicking the button below:</p>
        <div style="text-align:center;margin:30px 0;">
            <a href="{confirm_url}" style="background:#e8700a;color:white;padding:12px 30px;border-radius:8px;text-decoration:none;font-weight:bold;">
                Confirm Email
            </a>
        </div>
        <p style="color:#666;font-size:13px;">Or copy this link: {confirm_url}</p>
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <p style="color:#999;font-size:12px;text-align:center;">NetLedger by 2max Tech</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        return False


def _send_email_change_confirmation(smtp_settings: dict, to_email: str, full_name: str, token: str):
    """Send email change confirmation link to the NEW email address."""
    host = smtp_settings.get("smtp_host", "")
    port = int(smtp_settings.get("smtp_port", 587))
    user = smtp_settings.get("smtp_user", "")
    password = smtp_settings.get("smtp_password", "")
    from_addr = smtp_settings.get("smtp_from", user)
    from_name = smtp_settings.get("smtp_from_name", "NetLedger")

    if not host or not user:
        logger.warning("SMTP not configured, skipping email change confirmation")
        return False

    confirm_url = f"https://netl.2max.tech/login?verify_email={token}"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email
    msg["Subject"] = "Confirm your new email address - NetLedger"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
        <div style="text-align:center;margin-bottom:20px;">
            <h2 style="color:#e8700a;">NetLedger</h2>
        </div>
        <p>Hi {full_name},</p>
        <p>You requested to change your email address to <strong>{to_email}</strong>. Please confirm by clicking the button below:</p>
        <div style="text-align:center;margin:30px 0;">
            <a href="{confirm_url}" style="background:#e8700a;color:white;padding:12px 30px;border-radius:8px;text-decoration:none;font-weight:bold;">
                Confirm New Email
            </a>
        </div>
        <p style="color:#666;font-size:13px;">Or copy this link: {confirm_url}</p>
        <p style="color:#666;font-size:13px;">If you did not request this change, you can ignore this email.</p>
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <p style="color:#999;font-size:12px;text-align:center;">NetLedger by 2max Tech</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Failed to send email change confirmation: {e}")
        return False


@router.get("/verify-email")
async def verify_email_change(token: str, db: AsyncSession = Depends(get_db)):
    """Verify email change token and update user's email."""
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    role_field = payload.get("role", "")
    if not role_field.startswith("email_change:"):
        raise HTTPException(status_code=400, detail="Invalid verification token")

    new_email = role_field.replace("email_change:", "", 1)
    user_id = payload.get("sub")

    # Check new email isn't already taken
    existing = await db.execute(select(User).where(User.email == new_email, User.id != user_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already taken by another account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.email = new_email
    await db.flush()
    return {"message": f"Email updated to {new_email} successfully!"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check for duplicate username or email
    from sqlalchemy import or_
    existing = await db.execute(
        select(User).where(or_(User.username == body.username, User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        company_name=body.company_name,
        phone=body.phone,
        role=UserRole.admin,
        is_active=False,  # Inactive until email confirmed
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Send confirmation email
    token = create_access_token(str(user.id), "verify")
    smtp_settings = await _get_platform_smtp(db)
    sent = _send_confirmation_email(smtp_settings, body.email, body.full_name, token)

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "message": "Registration successful. Please check your email to confirm your account." if sent else "Registration successful. Please contact support to activate your account.",
        "email_sent": sent,
    }


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Verify email confirmation token and activate user."""
    payload = decode_token(token)
    if payload is None or payload.get("role") != "verify":
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_active:
        return {"message": "Account already verified"}

    user.is_active = True
    await db.flush()
    return {"message": "Email confirmed! You can now login."}
