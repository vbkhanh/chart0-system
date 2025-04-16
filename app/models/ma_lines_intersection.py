
from sqlalchemy import ForeignKey, Column, Integer, String, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class MA_Lines_Intersection(Base):
    line1_period = Column(Integer, nullable=False)
    line2_period = Column(Integer, nullable=False)
    bar_type = Column(String, nullable=False)
    points = Column(ARRAY(JSONB), nullable=False, default=[])
    symbol_id = Column(ForeignKey('symbol.id'), nullable=False)

    def __repr__(self):
        return f"<MA Lines Intersection(line1_period='{self.line1_period}, line2_period='{self.line2_period}', 'bar_type='{self.bar_type}')>"
    