from sqlalchemy import ForeignKey, String, Column
from .base import Base

class Snapshot(Base):
    title = Column(String(30), nullable=True)
    url = Column(String(255), nullable=False)
    user_id = Column(ForeignKey('user.id'), index=True, nullable=False)

    def __repr__(self):
        return f"<Snapshot(title='{self.title}', User ID='{self.user_id}')>"
    