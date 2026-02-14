from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database_models import User
from app.database import get_session
from app.config import SECRET_KEY, ALGORITHM
from app.core.logging_config import logger

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    
    # Convert sub to string if it's an integer
    if "sub" in to_encode and isinstance(to_encode["sub"], int):
        to_encode["sub"] = str(to_encode["sub"])
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.info(f"[AUTH] Created token for user {to_encode.get('sub')}: {encoded_jwt[:50]}...")
    
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decode and validate JWT token"""
    try:
        logger.info(f"[AUTH] Decoding token: {token[:50]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"[AUTH] Token decoded successfully for user: {payload.get('sub')}")
        return payload
    except JWTError as e:
        logger.error(f"[AUTH] Token decode failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Dependency to get current authenticated user"""
    logger.info(f"[AUTH] get_current_user called")
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    # Convert sub back to int for database lookup
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        logger.error(f"[AUTH] No user_id in token payload")
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user_id = int(user_id_str)
    logger.info(f"[AUTH] Looking up user_id: {user_id}")
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.error(f"[AUTH] User not found for id: {user_id}")
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        logger.error(f"[AUTH] User account disabled: {user.email}")
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    logger.info(f"[AUTH] User authenticated: {user.email}")
    return user
