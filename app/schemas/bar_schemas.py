from pydantic import BaseModel
from datetime import date


class BarOut(BaseModel):
    from_time: date
    to_time: date
    open: float
    high: float
    low: float
    close: float
    provisional_open: float | None
    provisional_close: float | None
   
    class Config:
        from_attributes = True

class BarPreviousDayPricesOut(BaseModel):
    symbol_id: int
    close: float
    high: float
    low: float
    class Config:
        from_attributes = True

    