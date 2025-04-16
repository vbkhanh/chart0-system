from pydantic import BaseModel
from datetime import date
from typing import List

class MAListPoint(BaseModel):
    date: date
    value: float
    class Config:
        from_attributes = True

class MA_ListOut(BaseModel):
    points: List[MAListPoint]
    class Config:
        from_attributes = True

class MA_ListOutV2(BaseModel):
    MA_5: List[MAListPoint]
    MA_10: List[MAListPoint]
    MA_20: List[MAListPoint]
    MA_50: List[MAListPoint]
    MA_100: List[MAListPoint]
    class Config:
        from_attributes = True
