from pydantic import BaseModel
from datetime import date


class TickOut(BaseModel):
    bid: float
    ask: float
    datetime_msc: int
   
    class Config:
        from_attributes = True

class LatestTickOut(BaseModel):
    symbol_id: int
    ask: float
    class Config:
        from_attributes = True

    