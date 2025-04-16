from pydantic import BaseModel
from datetime import datetime

class SnapshotOut(BaseModel):
    id: int
    title: str
    url: str
    created_at: datetime
    class Config:
        from_attributes = True