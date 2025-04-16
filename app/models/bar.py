from sqlalchemy import ForeignKey, Date, Column, Float, Integer, String, BIGINT
from .base import Base

class Bar(Base):
    from_time = Column(Date, nullable=False)
    to_time = Column(Date, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    provisional_open = Column(Float, nullable=True)
    provisional_close = Column(Float, nullable=True)
    volume = Column(BIGINT, nullable=False)
    type = Column(String, nullable=False)
    symbol_id = Column(ForeignKey('symbol.id'), nullable=False)
    tokyo_stock_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<Bar(symbol='{self.symbol_id}'>"
