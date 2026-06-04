import os
import secrets

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from nptmpl.core.config import ConfigManager
from nptmpl.server.deps import get_config


security = HTTPBearer()

def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security), 
                config: ConfigManager = Depends(get_config)) -> str:
    """Dependency that validates the Bearer token for API access."""
    expected_token = os.environ.get("NPTMPL_SERVER_TOKEN") or config.get_auth_token()

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Server security policy error: No API token configured on host.",
        )

    if not secrets.compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

def get_admin_user(request: Request, config: ConfigManager = Depends(get_config)) -> str:
    """
    Dependency that validates the user is logged in via session.
    If not authenticated, it raises a 401 which is handled by a redirect to /login.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user
