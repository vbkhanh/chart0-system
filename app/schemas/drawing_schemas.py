from pydantic import BaseModel

class DrawingIn(BaseModel):
    data: dict
    symbol_id: int
    user_id: int

class DrawingOut(BaseModel):
    id: int
    data: dict
    symbol_id: int

    class Config:
        from_attributes = True

class DrawingData(BaseModel):
    data: dict