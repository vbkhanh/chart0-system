from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SymbolOut(BaseModel):
    id: int
    name: str
    description: str
    symbol_info: dict
    category: str
    code: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class MAIntersectionSymbolOut(BaseModel):
    symbol_id: int
    name: str
    symbol_info: dict
    japanese_name: Optional[str]
    description: str
    category : str
    class Config:
        from_attributes = True

class MAIntersectionBarOut(BaseModel):
    symbol_id: int
    high: float
    low: float
    price: float
    compare_to_previous_tick: Optional[bool] = None
    change: float
    change_percentage: float
    class Config:
        from_attributes = True

class CategorySetUp(BaseModel):
    new_category: str
    