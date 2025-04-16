from typing import List
from sqlalchemy import String, CheckConstraint, Column
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class Symbol(Base):
    name = Column(String(255), index=True, unique=True, nullable=False)
    description = Column(String(255), nullable=False)
    symbol_info = Column(JSONB, nullable=False)
    category = Column(String(255), nullable=True)
    code = Column(String(30), unique=True, nullable=True, default=None)
    japanese_name = Column(String(255), nullable=True)
    
    __table_args__ = (
        CheckConstraint("category IN ('Stock', 'Forex', 'Commodities', 'Indices')", name="category_check"),
    )

    def __repr__(self):
        return f"<Symbol(name='{self.name}', description='{self.description}')>"
    