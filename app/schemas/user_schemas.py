from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date
class UserCreate(BaseModel):
    full_name: str
    hiragana_name: Optional[str] = None
    date_of_birth: date | None = None
    email: EmailStr
    phone_number: str
    password: str

class UserIn(BaseModel):
    full_name: str
    hiragana_name: Optional[str] = None
    date_of_birth: date | None = None
    email: EmailStr
    phone_number: str

class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone_number: str | None
    date_of_birth: date | None
    hiragana_name: Optional[str] = None
    status: str
    state: str
    created_at: datetime

    class Config:
        from_attributes = True
class UserOutMe(BaseModel):
    full_name: str
    hiragana_name: Optional[str] = None
    email: EmailStr
    phone_number: str | None
    date_of_birth: date | None
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserStatusChange(BaseModel):
    new_status: str

class UserStateChange(BaseModel):
    new_state: str

class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserEmail(BaseModel):
    email: EmailStr

class UserOTP(BaseModel):
    email: str
    OTP: str

class UserResetPassword(BaseModel):
    new_password: str