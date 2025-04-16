from sqlalchemy import ForeignKey, String, Column
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class Drawing(Base):
    data = Column(JSONB, nullable=False)
    symbol_id = Column(ForeignKey('symbol.id'), index=True, nullable=False)
    user_id = Column(ForeignKey('user.id'), index=True, nullable=False)
    
    def __repr__(self):
        return f"<Drawing(Symbol ID='{self.symbol_id}')>"
    