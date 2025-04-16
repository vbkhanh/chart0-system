from datetime import datetime
from sqlalchemy import BIGINT, ForeignKey, Column, Float, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
    
class Tick(Base):
    datetime_msc = Column(BIGINT, nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    last = Column(Float, nullable=False)
    volume = Column(INTEGER, nullable=False)
    symbol_id = Column(ForeignKey('symbol.id'), nullable=False)

    def __repr__(self):
        return f"<Tick(symbol='{self.symbol_id}'>"