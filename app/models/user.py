from sqlalchemy import String, CheckConstraint, Boolean, Column
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import DATE
from .base import Base


class User(Base):
    full_name = Column(String(255), nullable=False)
    hiragana_name = Column(String(255), nullable=True)
    date_of_birth = Column(DATE, nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(255), nullable=True)
    encrypted_password = Column(String(255), nullable=False)
    role = Column(String(255), default="user", nullable=False)
    status = Column(String(255), default="pending", nullable=False)
    state = Column(String(255), default="disabled", nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="status_check"),
        CheckConstraint("state IN ('enabled', 'disabled')", name="state_check")
    )

    def __repr__(self):
        return f"<User(name='{self.full_name}'>"