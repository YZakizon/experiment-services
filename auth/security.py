from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status
from config import config

# This list would typically be loaded securely from a .env file
# VALID_TOKENS = {"my_secret_api_key_123"} 

# Instantiate the HTTP Bearer scheme
bearer_scheme = HTTPBearer()

def get_current_client(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Validates the Bearer token for every secured endpoint."""
    if credentials.scheme != "Bearer" or credentials.credentials not in config.valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Returns the token value, which can be used to identify the client if needed
    return credentials.credentials