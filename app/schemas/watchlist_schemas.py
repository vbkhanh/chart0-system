from pydantic import BaseModel, Json

from typing import Optional


class WatchlistIn(BaseModel):
    title: str
    sections: list[dict]
    
class WatchlistOut(BaseModel):
    id: int
    title: str
    sections: list[dict]

    class Config:
        from_attributes = True

class WatchListBarOut(BaseModel):
    symbol_id: int
    price: float
    change: float
    change_percentage: float
    compare_to_previous_tick: Optional[bool] = None

    class Config:
        from_attributes = True