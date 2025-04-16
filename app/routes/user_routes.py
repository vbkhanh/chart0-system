from fastapi import APIRouter, status, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update, delete, func
from datetime import datetime, date, timedelta, time
from sqlalchemy.ext.asyncio import AsyncSession
from app.configs.db import get_session
from app.schemas import user_schemas
from app.models import User, Snapshot, Watchlist
from typing import Annotated
from app.utils import get_current_admin, get_current_user
from app.utils import hash_password, verify_password
import logging
from app.configs.mail_sender import send_mail
from app.email_templates.email_subject_constants import APPROVE_USER_SUBJECT, DISABLED_ACCOUNT_SUBJECT, ENABLED_ACCOUNT_SUBJECT, DELETE_ACCOUNT_SUBJECT
from app.constants import CLIENT_TIMEZONE

router = APIRouter(
    prefix="/users"
)

logger = logging.getLogger(__name__)

@router.post("/createadmin", response_model=user_schemas.UserOut)
async def create_user(user: user_schemas.UserCreate, session:AsyncSession = Depends(get_session)):
    try:
        encrypted_password = hash_password(user.password)
        new_user = User(full_name=user.full_name, hiragana_name=user.hiragana_name, date_of_birth=user.date_of_birth, phone_number=user.phone_number, email=user.email, encrypted_password=encrypted_password, role="admin", status="approved", state="enabled", is_verified=True)     
        session.add(new_user)
        await session.commit()
    finally:
        await session.close()
    return new_user

@router.get("", response_model=dict[str, int | list[user_schemas.UserOut]])
async def get_users(
    id: int | None = None, full_name: str | None = None, date_of_birth: list[date] | None = Query(default=None), email: str | None = None, 
    phone_number: str | None = None, created_at: list[date] | None = Query(default=None), status: str | None = None, hiragana_name: str | None = None,
    session: AsyncSession = Depends(get_session), offset: int = 0, limit: Annotated[int, Query(le=100)] = 100,
    current_admin: HTTPAuthorizationCredentials = Depends(get_current_admin)
):
    try:
        query_params = locals().copy()
        query_params.pop("session")
        query_params.pop("offset")
        query_params.pop("limit")
        query_params.pop("current_admin")

        filter_options = {key: value for key, value in query_params.items() if value is not None}

        query = select(User.id, User.full_name, User.email, User.phone_number, User.date_of_birth, User.status, User.state, User.created_at, User.hiragana_name)
        count_query = select(func.count(User.id))

        if filter_options:
            for key, value in filter_options.items():
                if key == "id":
                    query = query.filter(getattr(User, key) == value)
                    count_query = count_query.filter(getattr(User, key) == value)
                elif key == "date_of_birth" or key == "created_at":
                    if len(value) == 2:
                        query = query.filter(getattr(User,key)>=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE), getattr(User,key)<=datetime.combine(value[1], time.min)-timedelta(hours=CLIENT_TIMEZONE))
                        count_query = count_query.filter(getattr(User,key)>=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE), getattr(User,key)<=datetime.combine(value[1], time.min)-timedelta(hours=CLIENT_TIMEZONE))
                    elif len(value) == 1:
                        query = query.filter(getattr(User,key)>=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE), getattr(User,key)<=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE))
                        count_query = count_query.filter(getattr(User,key)>=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE), getattr(User,key)<=datetime.combine(value[0], time.min)-timedelta(hours=CLIENT_TIMEZONE))
                else:
                    query = query.filter(func.lower(getattr(User, key)).like(f"%{value.lower()}%"))
                    count_query = count_query.filter(func.lower(getattr(User, key)).like(f"%{value.lower()}%"))

            query = query.filter(User.role=="user").filter(User.is_verified!=False).order_by(User.created_at.desc()).offset(offset).limit(limit)
            count_query = count_query.filter(User.role=="user").filter(User.is_verified!=False)

            users = await session.execute(query)
            total_users = await session.scalars(count_query)
        else:
            users = await session.execute(query.where(User.role=="user").where(User.is_verified!=False).order_by(User.created_at.desc()).offset(offset).limit(limit))
            total_users = await session.scalars(count_query.filter(User.role=="user").where(User.is_verified!=False))

        users = users.all()
        total_users = total_users.first()

    finally:
        await session.close()
    
    return {
        "total_users": total_users,
        "users": users
    }

@router.get("/me", response_model=user_schemas.UserOutMe)
async def get_user(session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        user = await session.execute(select(User.full_name, User.hiragana_name, User.email, User.phone_number, User.date_of_birth).where(User.id==current_user.id))
        user = user.first()
    
    finally:
        await session.close()
    
    return user


@router.patch("/edit_me", response_model=None)
async def edit_user(user_profile:user_schemas.UserIn, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
    
        result = await session.execute(update(User).where(User.id==current_user.id).values(
            full_name=user_profile.full_name,
            hiragana_name=user_profile.hiragana_name,
            email=user_profile.email,
            phone_number=user_profile.phone_number,
            date_of_birth=user_profile.date_of_birth
        ))
        await session.commit()

    except Exception as e:
        logger.error(f"Error while editing user profile: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_editing_user_profile")
    
    finally:
        await session.close()
    
    return {"message": "successfully_edit_user_profile"}


@router.patch("/{id}/new_user_status", response_model=None)
async def change_user_status(
    id:int, user_status:user_schemas.UserStatusChange, session:AsyncSession = Depends(get_session),
    current_admin: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    try:
        user = await session.execute(select(User.full_name, User.email, User.status).where(User.id == id))

        user = user.first()

        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
        if user_status.new_status == "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_user_status")
        elif user.status == "approved":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_already_approved")
    
        result = await session.execute(update(User).where(User.id==id).values(status=user_status.new_status))
    
        if user_status.new_status == "approved":
            result = await session.execute(update(User).where(User.id==id).values(state="enabled"))
            did_send_mail = send_mail(user.email, APPROVE_USER_SUBJECT, "approve_user_request.jinja", full_name=user.full_name)
        elif user_status.new_status == "rejected":
            did_send_mail = send_mail(user.email, APPROVE_USER_SUBJECT, "reject_user_request.jinja", full_name=user.full_name)

        await session.commit()
    
    except Exception as e:
        logger.error(f"Error while setting user status: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_setting_user_status")  
    
    finally:
        await session.close()  
    
    return {"message": "successfully_change_user_status"}

@router.patch("/{id}/new_user_state", response_model=None)
async def switch_user_state(
    id:int, user_state:user_schemas.UserStateChange, session:AsyncSession = Depends(get_session),
    current_admin: HTTPAuthorizationCredentials = Depends(get_current_admin)
):
    try:
        user = await session.execute(select(User.full_name, User.email, User.status).where(User.id == id))

        user = user.first()

        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
        if user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
    
        result = await session.execute(update(User).where(User.id==id).values(state=user_state.new_state))
        await session.commit()

        if user_state.new_state == "disabled":
            did_send_mail = send_mail(user.email, DISABLED_ACCOUNT_SUBJECT, "disabled_account.jinja", full_name=user.full_name)
        else:
            did_send_mail = send_mail(user.email, ENABLED_ACCOUNT_SUBJECT, "enabled_account.jinja", full_name=user.full_name)

    except Exception as e:
        logger.error(f"Error while setting user state: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_setting_user_state") 
    
    finally:
        await session.close()   
    
    return {"message": "successfully_change_user_state"}

@router.delete("/{id}", response_model=None)
async def delete_user(id:int, session:AsyncSession = Depends(get_session), current_admin: HTTPAuthorizationCredentials = Depends(get_current_admin)) -> dict[str, str]:
    try:
        user = await session.execute(select(User.full_name, User.email).where(User.id == id))

        user = user.first()

        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
        
        # Remove snapshots associated with the user
        await session.execute(delete(Snapshot).where(Snapshot.user_id == id))
        
        # Remove watchlists associated with the user
        await session.execute(delete(Watchlist).where(Watchlist.user_id == id))
        
        # Remove the user
        await session.execute(delete(User).where(User.id == id))
        
        await session.commit()

        did_send_mail = send_mail(user.email, DELETE_ACCOUNT_SUBJECT, "deleted_account.jinja", full_name=user.full_name)
    
    except Exception as e:
        logger.error(f"Error while deleting user: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_deleting_user")
    
    finally:
        await session.close() 
    
    return {"message": "successfully_delete_user"}

@router.patch("/new_password", response_model=None)
async def change_password(user_password:user_schemas.UserPasswordChange, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        user_old_password = await session.scalars(select(User.encrypted_password).where(User.id == current_user.id))

        user_old_password = user_old_password.first()
        
        if not verify_password(user_password.old_password, user_old_password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="incorrect_old_password")
        
        try:
            encrypted_password = hash_password(user_password.new_password)
            result = await session.execute(update(User).where(User.id==current_user.id).values(encrypted_password=encrypted_password))
            await session.commit()
        except Exception as e:
            logger.error(f"Error while changing user password: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_changing_user_password")
    
    finally:
        await session.close()   
    
    return {"message": "successfully_change_user_password"}
