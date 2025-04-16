from passlib.context import CryptContext
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.requests import Request
from app.settings import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.models.user import User
from app.schemas import token_schemas
from app.configs.db import get_session
from app.constants import (
    JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES, OTP_LENGTH
)
import logging
import math, random
import string
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/login')

admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/adminlogin')


def get_blob_sas_token(container_name: str, blob_name: str) -> str:
    sas_token = generate_blob_sas(
        account_name=settings.BLOB_ACCOUNT_NAME,
        account_key=settings.BLOB_ACCOUNT_KEY,
        container_name=container_name,
        blob_name=blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now() + timedelta(minutes=10)
    )

    return sas_token

def generate_OTP():
    OTP = ""
    OTP_DIGITS = string.digits

    for i in range(OTP_LENGTH):
        OTP += OTP_DIGITS[math.floor(random.random() * 10)]

    return OTP

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expire_minutes: int = None) -> str:
    if expire_minutes is None:
        expire_time = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire_time = datetime.now() + timedelta(minutes=expire_minutes)
    
    data.update({"exp": expire_time.timestamp()})

    encoded_jwt = jwt.encode(data, settings.JWT_SECRET_KEY, JWT_ALGORITHM)
    
    return encoded_jwt

def create_refresh_token(data: dict, expire_minutes: int = None) -> str:    
    if expire_minutes is None:
        expire_time = datetime.now() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    else:
        expire_time = datetime.now() + timedelta(minutes=expire_minutes)
    
    data.update({"exp": expire_time.timestamp()})

    encoded_jwt = jwt.encode(data, settings.JWT_SECRET_KEY, JWT_ALGORITHM)

    return encoded_jwt

def verify_access_token(token: str, credentials_exception) -> bool:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=JWT_ALGORITHM)
        
        id : int = payload.get("user_id")
        role : str = payload.get("user_role")

        if id is None or role is None:
            raise credentials_exception
        
        token_data = token_schemas.DataToken(user_id=id, user_role=role, exp=None)
       
    except jwt.exceptions.InvalidTokenError as e:
        logging.info(f"Error verifying token: {e}")
        raise credentials_exception
    
    return token_data

def verify_refresh_token(token: str, credentials_exception) -> bool:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=JWT_ALGORITHM)

        id : int = payload.get("user_id")
        role : str = payload.get("user_role")
        exp : float = payload.get("exp")

        if id is None or role is None or exp is None:
            raise credentials_exception
        
        token_data = token_schemas.DataToken(user_id=id, user_role=role, exp=exp)

    except jwt.exceptions.InvalidTokenError as e:
        logging.info(f"Error verifying token: {e}")
        raise credentials_exception

    return token_data

async def authenticate_basic(
    request: Request
) -> HTTPAuthorizationCredentials:
    authorization = request.headers.get("Authorization")
    scheme, credentials = get_authorization_scheme_param(authorization)
    if not (authorization and scheme and credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized"
        )
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalidScheme"
        )
    return HTTPAuthorizationCredentials(
        scheme=scheme, credentials=credentials
    )

class AuthenticationUserRole(HTTPBearer):
    async def __call__(
        self, request: Request,
        session: AsyncSession = Depends(get_session),
    ) -> HTTPAuthorizationCredentials:
        try:
            credential: HTTPAuthorizationCredentials = (
                await authenticate_basic(request)
            )
            credentials_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                          detail="invalid_token",
                                          headers={"WWW-Authenticate": "Bearer"})
    
            verified_token_data = verify_access_token(credential.credentials, credentials_exception)

            user = await session.execute(select(User.id, User.role, User.status, User.state).where(User.id == verified_token_data.user_id))
            user = user.first()
            
            if user is None:
                raise credentials_exception
        finally:
            await session.close()
        return user
    
class AuthenticationAdminRole(HTTPBearer):
    async def __call__(
        self, request: Request,
        session: AsyncSession = Depends(get_session),
    ) -> HTTPAuthorizationCredentials:
        try:
            credential: HTTPAuthorizationCredentials = (
                await authenticate_basic(request)
            )
            credentials_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                          detail="invalid_token",
                                          headers={"WWW-Authenticate": "Bearer"})
    
            verified_token_data = verify_access_token(credential.credentials, credentials_exception)
            logging.info(verified_token_data)

            if verified_token_data.user_role != "admin":
                raise credentials_exception
            
            admin = await session.execute(select(User.id, User.role, User.status, User.state).where(User.id == verified_token_data.user_id))
            admin = admin.first()

            if admin is None:
                raise credentials_exception
        finally:
            await session.close()
        return admin

get_current_user = AuthenticationUserRole()
get_current_admin = AuthenticationAdminRole()
