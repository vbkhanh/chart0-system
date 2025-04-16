from sqlalchemy import String, Column
from .base import Base


class Indicator(Base):
    name = Column(String(255), index=True, nullable=False)

    def __repr__(self):
        return f"<Indicator(indicator_name='{self.name}'"