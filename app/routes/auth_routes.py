from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Annotated
from app.configs.db import get_session
from app.configs.redis import redis_client
from app.schemas import token_schemas, user_schemas
from app.models.user import User
from app.constants import REFRESH_TOKEN_EXPIRE_MINUTES, OTP_EXPIRE_MINUTES, PASSWORD_RESET_EXPIRE_MINUTES
from app.utils import verify_password, create_access_token, hash_password, create_refresh_token, verify_refresh_token, get_current_user, generate_OTP
from app.configs.mail_sender import send_mail
from app.email_templates.email_subject_constants import ACCOUNT_VERIFICATION_SUBJECT, FORGOT_PASSWORD_SUBJECT
from app.settings import settings
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(
    prefix=""
)

@router.post('/adminlogin', response_model=token_schemas.Token)
async def login(user_login: user_schemas.UserLogin, session: AsyncSession = Depends(get_session)):
    try:
        user = await session.execute(select(User.id, User.role, User.encrypted_password).where(User.email == user_login.email))
        user = user.first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_exist")
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_is_not_an_admin")
        if not verify_password(user_login.password, user.encrypted_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect_password")
        
        access_token = create_access_token(data={"user_id": user.id, "user_role": user.role})
        refresh_token = create_refresh_token(data={"user_id": user.id, "user_role": user.role})
        
        redis_client.setex(
            refresh_token,
            timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
            value=user.id
        )
    finally:
        await session.close()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token, 
        "token_type": "bearer"
    }

@router.post("/signup", response_model=None)
async def register_user(user: user_schemas.UserCreate, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        existing_user_id = await session.scalars(select(User.id).where(User.email == user.email))
        existing_user_id = existing_user_id.first()
        if existing_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email_already_existed")
        
        encrypted_password = hash_password(user.password)
    
        new_user = User(
            full_name=user.full_name, hiragana_name=user.hiragana_name, 
            date_of_birth=user.date_of_birth, 
            phone_number=user.phone_number, 
            email=user.email, 
            encrypted_password=encrypted_password
        )     

        session.add(new_user)

        await session.commit()

        OTP = generate_OTP()
        
        did_send_mail = send_mail(user.email, ACCOUNT_VERIFICATION_SUBJECT, "account_verification.jinja", full_name=new_user.full_name, OTP=OTP)
            
        if did_send_mail == False:
            return {
                "OTP": OTP
            }

        redis_client.setex(
            new_user.email,
            timedelta(minutes=OTP_EXPIRE_MINUTES),
            value=OTP
        )
    finally:
        await session.close()
        
    return {
        "message":"sent_verification_email",
    }


@router.post('/login', response_model=token_schemas.Token)
async def login(user_login: user_schemas.UserLogin, session:AsyncSession = Depends(get_session)):
    try:
        user = await session.execute(select(User.id, User.role, User.status, User.state, User.is_verified, User.encrypted_password).where(User.email == user_login.email))
        user = user.first()
    
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_exist")
        if user.is_verified == False:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_verified!")
        if user.status != "approved" or user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved_or_enabled.")
        if not verify_password(user_login.password, user.encrypted_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect_password")
        
        access_token = create_access_token(data={"user_id": user.id, "user_role": user.role})
        refresh_token = create_refresh_token(data={"user_id": user.id, "user_role": user.role})
        
        redis_client.setex(
            refresh_token,
            timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
            value=user.id
        )
    finally:
        await session.close()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token, 
        "token_type": "bearer"
    }


@router.post('/logout', response_model=None)
async def logout(token: token_schemas.RefreshToken, current_user:Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    redis_client.delete(token.refresh_token)

    return {"message": "success"}


@router.post('/refresh', response_model=token_schemas.Token)
async def refresh_token(token: token_schemas.RefreshToken):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                          detail="fail_to_validate_credentials",
                                          headers={"WWW-Authenticate": "Bearer"})
    
    user_id = redis_client.get(token.refresh_token)

    if user_id is None:
        raise credentials_exception
    
    user_id = int(user_id.decode('utf-8'))
    
    verified_token_data = verify_refresh_token(token.refresh_token, credentials_exception)

    if user_id != verified_token_data.user_id:
        raise credentials_exception

    new_access_token = create_access_token(data={"user_id": verified_token_data.user_id, "user_role": verified_token_data.user_role})
    
    new_refresh_token = create_refresh_token(data={"user_id": verified_token_data.user_id, "user_role": verified_token_data.user_role})
    
    redis_client.delete(token.refresh_token)

    redis_client.setex(
        new_refresh_token,
        timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
        value=verified_token_data.user_id
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post('/verify_OTP', response_model=None)
async def verify_OTP(user_OTP:user_schemas.UserOTP, session: AsyncSession = Depends(get_session)):
    OTP = redis_client.get(user_OTP.email)

    if OTP is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="otp_has_expired")
    
    OTP = OTP.decode('utf-8')

    if OTP != user_OTP.OTP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="incorrect_otp")
    redis_client.delete(user_OTP.email)

    try:
        result = await session.execute(update(User).where(User.email==user_OTP.email).values(is_verified=True))
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error while verifying user: {e}")
    finally:
        await session.close()    

    return {"message": "success"}

@router.post('/resend_OTP', response_model=None)
async def resend_OTP(user_email: user_schemas.UserEmail, session:AsyncSession = Depends(get_session)):
    OTP = redis_client.get(user_email.email)

    if OTP is None:
        OTP = generate_OTP()
    else:
        OTP = OTP.decode('utf-8')
    
        
    user_full_name = await session.scalars(select(User.full_name).where(User.email == user_email.email))
    user_full_name = user_full_name.first()

    did_send_mail = send_mail(user_email.email, ACCOUNT_VERIFICATION_SUBJECT, "account_verification.jinja", full_name=user_full_name, OTP=OTP)
        
    if did_send_mail == False:
        return {
            "OTP": OTP
        }

    redis_client.setex(
        user_email.email,
        timedelta(minutes=OTP_EXPIRE_MINUTES),
        value=OTP
    )
        
    return {
        "message":"sent_verification_email",
    }
    

@router.post('/forgot_password', response_model=None)
async def send_email_to_reset_password(user_email: user_schemas.UserEmail, session:AsyncSession = Depends(get_session)):
    try:
        user = await session.execute(select(User.id, User.full_name, User.role).where(User.email == user_email.email))
        user = user.first()

        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_not_exist")
        
        access_token = create_access_token(data={"user_id": user.id, "user_role": user.role}, expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES)
        reset_link = settings.PASSWORD_RESET_LINK + f"?token={access_token}"
        
        did_send_mail = send_mail(user_email.email, FORGOT_PASSWORD_SUBJECT, "forgot_password.jinja", full_name=user.full_name, reset_link=reset_link)
        
        if did_send_mail == False:
            return {
                "password_reset_link": reset_link
            }
    finally:
        await session.close()
    
    return {
        "message":"send_password_reset_email"
    }

    
@router.post('/forgot_password/reset', response_model=None)
async def reset_password(user_reset_password: user_schemas.UserResetPassword, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)):
    
    if current_user.status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
    if current_user.state != "enabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
    
    try:
        encrypted_password = hash_password(user_reset_password.new_password)
        result = await session.execute(update(User).where(User.id==current_user.id).values(encrypted_password=encrypted_password))
        await session.commit()
    except Exception as e:
        print(f"Error while resetting user password: {e}") 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reset_password_failed")
    finally:
        await session.close()
