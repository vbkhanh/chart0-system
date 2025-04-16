from sqlalchemy import ForeignKey, String, ARRAY, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class Watchlist(Base):
    title = Column(String(30), index=True, nullable=False)
    sections = Column(ARRAY(JSONB), nullable=False, default=[])
    user_id = Column(ForeignKey('user.id'))

    def __repr__(self):
        return f"<Watchlist(name='{self.title}', User ID='{self.user_id}')>"
    