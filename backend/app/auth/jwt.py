import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# IMPORTANT: Store this securely, e.g., in environment variables.
# For demonstration, a default is provided, but this is a security risk in production.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-please-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if JWT_SECRET_KEY == "your-secret-key-here-please-change":
    print("WARNING: Using default JWT_SECRET_KEY. This is insecure. Please set a strong secret key in your environment.")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token") # Adjusted tokenUrl to match future auth router

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception: HTTPException) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        # You could add more checks here, e.g., for 'sub' (username) field
        username: Optional[str] = payload.get("sub")
        if username is None: # Basic check if username (subject) is in token
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
    except Exception: # Catch any other unexpected error during decode
        raise credentials_exception
