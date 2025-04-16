from sqlalchemy.sql import func
from sqlalchemy import DateTime, BIGINT, Column
from datetime import datetime

from app.configs.db import BaseMixin, BaseModel

class Base(BaseMixin, BaseModel):
    __abstract__ = True

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime, server_default=func.now(), default=datetime.now, nullable=False
    )
