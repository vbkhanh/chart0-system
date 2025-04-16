from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class DataToken(BaseModel):
    user_id: int | None
    user_role: str | None 
    exp: float | None 

class RefreshToken(BaseModel):
    refresh_token: str