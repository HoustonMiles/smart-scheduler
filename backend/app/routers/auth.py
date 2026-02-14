from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta
import secrets
import logging

from app.database import get_session
from app.models.database_models import User, UserSettingsDB, AuthSessionDB
from app.core.auth.jwt import create_access_token, get_current_user
from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    SCOPES,
)
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter()
logger = logging.getLogger(__name__)

AUTH_SESSION_TIMEOUT_MINUTES = 10


@router.get("/login")
async def login(
    session_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Start OAuth flow - creates auth session and redirects to Google.
    Extension opens this URL and polls /auth/poll/{session_id}
    """
    logger.info(f"Login initiated with session_id: {session_id}")
    
    # Generate OAuth parameters
    state = secrets.token_urlsafe(32)
    
    # Create flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=state,
        prompt='consent'
    )
    
    # Store session in database (using UTC time without timezone info)
    auth_session = AuthSessionDB(
        session_id=session_id,
        state=state,
        code_verifier=state,  # Using state as verifier for simplicity
        completed=False,
        expires_at=datetime.utcnow() + timedelta(minutes=AUTH_SESSION_TIMEOUT_MINUTES)
    )
    
    session.add(auth_session)
    await session.commit()
    
    logger.info(f"Created auth session, redirecting to Google")
    
    return RedirectResponse(url=authorization_url)


@router.get("/auth/poll/{session_id}")
async def poll_auth_status(
    session_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Extension polls this endpoint to check if OAuth completed.
    Returns JWT token when ready.
    """
    result = await session.execute(
        select(AuthSessionDB).where(AuthSessionDB.session_id == session_id)
    )
    auth_session = result.scalar_one_or_none()
    
    if not auth_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check expiration
    if datetime.utcnow() > auth_session.expires_at:
        await session.delete(auth_session)
        await session.commit()
        raise HTTPException(status_code=410, detail="Session expired")
    
    # Not completed yet
    if not auth_session.completed:
        return {"authenticated": False, "status": "pending"}
    
    # Completed! Return token
    return {
        "authenticated": True,
        "token": auth_session.access_token,
        "email": auth_session.user_email
    }


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Google redirects here after user approves.
    Exchange code for tokens, create/update user, generate JWT.
    """
    logger.info(f"OAuth callback received")
    
    # Find session by state
    result = await session.execute(
        select(AuthSessionDB).where(
            AuthSessionDB.state == state,
            AuthSessionDB.completed == False
        )
    )
    auth_session = result.scalar_one_or_none()
    
    if not auth_session:
        return HTMLResponse("""
            <html>
                <body style="font-family: monospace; padding: 40px; text-align: center;">
                    <h2>❌ Session Not Found</h2>
                    <p>This login session has expired or is invalid.</p>
                    <p>Please try logging in again from the extension.</p>
                </body>
            </html>
        """)
    
    # Check expiration
    if datetime.utcnow() > auth_session.expires_at:
        await session.delete(auth_session)
        await session.commit()
        return HTMLResponse("""
            <html>
                <body style="font-family: monospace; padding: 40px; text-align: center;">
                    <h2>⏰ Session Expired</h2>
                    <p>This login session has expired.</p>
                    <p>Please try logging in again from the extension.</p>
                </body>
            </html>
        """)
    
    try:
        # Exchange code for tokens
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                }
            },
            scopes=SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
            state=state
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user info from Google
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        
        email = user_info.get('email')
        google_id = user_info.get('id')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        logger.info(f"User authenticated: {email}")
        
        # Create or update user
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            user.last_login = datetime.utcnow()
            user.name = name
            user.picture = picture
        else:
            # Create new user
            user = User(
                email=email,
                google_id=google_id,
                name=name,
                picture=picture,
                is_active=True
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # Create default settings for new user
            settings = UserSettingsDB(
                user_id=user.id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=",".join(credentials.scopes) if credentials.scopes else "",
                min_hour=9,
                max_hour=18,
                buffer_minutes=60
            )
            session.add(settings)
        
        # Update existing user's tokens
        result = await session.execute(
            select(UserSettingsDB).where(UserSettingsDB.user_id == user.id)
        )
        settings = result.scalar_one_or_none()
        
        if settings:
            settings.access_token = credentials.token
            settings.refresh_token = credentials.refresh_token
            settings.token_uri = credentials.token_uri
            settings.client_id = credentials.client_id
            settings.client_secret = credentials.client_secret
            settings.scopes = ",".join(credentials.scopes) if credentials.scopes else ""
        
        await session.commit()
        
        # Generate JWT token
        jwt_token = create_access_token({"sub": user.id, "email": user.email})
        
        # Update auth session with token
        auth_session.access_token = jwt_token
        auth_session.user_email = email
        auth_session.completed = True
        
        await session.commit()
        
        logger.info(f"Login successful for {email}")
        
        return HTMLResponse("""
            <html>
                <head>
                    <style>
                        body {
                            font-family: 'Roboto', 'Arial', sans-serif;
                            padding: 40px;
                            text-align: center;
                            background: #f5f5f5;
                        }
                        .success-box {
                            background: white;
                            border: 3px solid #34a853;
                            border-radius: 8px;
                            padding: 40px;
                            max-width: 400px;
                            margin: 0 auto;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        }
                        h2 { color: #34a853; margin: 0 0 20px 0; }
                        p { margin: 10px 0; color: #5f6368; }
                    </style>
                </head>
                <body>
                    <div class="success-box">
                        <h2>✓ Authentication Successful!</h2>
                        <p>You can close this window now.</p>
                        <p style="margin-top: 20px; font-size: 12px; opacity: 0.7;">
                            Return to the extension to continue.
                        </p>
                    </div>
                    <script>
                        // Auto-close after 2 seconds
                        setTimeout(() => window.close(), 2000);
                    </script>
                </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"OAuth error: {e}", exc_info=True)
        await session.delete(auth_session)
        await session.commit()
        
        return HTMLResponse(f"""
            <html>
                <body style="font-family: monospace; padding: 40px; text-align: center;">
                    <h2>❌ Authentication Failed</h2>
                    <p>Error: {str(e)}</p>
                    <p>Please try logging in again from the extension.</p>
                </body>
            </html>
        """)


@router.get("/auth/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture
    }


@router.get("/auth/status")
async def auth_status():
    """Public endpoint to check if auth system is working"""
    return {
        "authenticated": False,
        "message": "Please login"
    }


@router.post("/auth/cleanup")
async def cleanup_expired_sessions(
    session: AsyncSession = Depends(get_session)
):
    """Cleanup expired auth sessions (call periodically)"""
    result = await session.execute(
        delete(AuthSessionDB).where(
            AuthSessionDB.expires_at < datetime.utcnow()
        )
    )
    
    deleted_count = result.rowcount
    await session.commit()
    
    logger.info(f"Cleaned up {deleted_count} expired auth sessions")
    
    return {"deleted": deleted_count}
