from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .jwt import verify_token, oauth2_scheme, JWT_SECRET_KEY, ALGORITHM # Added JWT_SECRET_KEY, ALGORITHM for consistency if needed by verify_token
from .schemas import User, TokenData
from .crud import get_user

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_payload = verify_token(token, credentials_exception)

    if token_payload is None: # Should be handled by verify_token raising exception
        raise credentials_exception

    username: str = token_payload.get("sub") # 'sub' is standard claim for subject (username)
    if username is None:
        raise credentials_exception

    user = get_user(username)
    if user is None:
        raise credentials_exception
    return User(**user.dict(exclude={"hashed_password"})) # Ensure returning User model

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
