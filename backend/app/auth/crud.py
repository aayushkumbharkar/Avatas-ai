from typing import Optional
from .schemas import User, UserInDB
# from passlib.context import CryptContext # Will be used when actual hashing is implemented

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") # For actual password hashing

# --- FAKE DATABASE AND USER HANDLING ---
# IMPORTANT: This is a placeholder and highly insecure for production.
# Passwords are not hashed securely (or at all in authenticate_user).
# User data is hardcoded.

# Example of how hashing would work with passlib:
# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password):
#     return pwd_context.hash(password)

# For now, using very simple placeholder passwords and structure.
# Real hashed passwords would be long strings. e.g. "$2b$12$EixZaYVK1fsj9LpY.8sV3OagL3gqiH9Bv2pGvj8W1.WaqX.n2Yy/O"
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "testpassword",  # In a real scenario, this would be a bcrypt hash
        "disabled": False,
    },
    "janeadmin": {
        "username": "janeadmin",
        "full_name": "Jane Admin",
        "email": "janeadmin@example.com",
        "hashed_password": "adminpassword", # In a real scenario, this would be a bcrypt hash
        "disabled": False,
    },
    "disableduser": {
        "username": "disableduser",
        "full_name": "Disabled User",
        "email": "disabled@example.com",
        "hashed_password": "password",
        "disabled": True,
    },
    "testuser": {
        "username": "testuser",
        "full_name": "Test User",
        "email": "testuser@example.com",
        "hashed_password": "testpassword", # Plain text for test purposes
        "disabled": False,
    }
}

def get_user(username: str) -> Optional[UserInDB]:
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticates a user.
    IMPORTANT: This current implementation directly compares plain text passwords
                 and does NOT use secure password hashing (like bcrypt).
                 This is for demonstration purposes ONLY and is INSECURE.
                 In a real application, use something like:
                 user = get_user(username)
                 if not user or not verify_password(password, user.hashed_password):
                     return None
                 return User(**user.dict())
    """
    user = get_user(username)
    if not user:
        return None
    # SECURITY RISK: Direct password comparison.
    if password == user.hashed_password: # This should be verify_password(password, user.hashed_password)
        return User(**user.dict(exclude={"hashed_password"})) # Return User model, not UserInDB
    return None
