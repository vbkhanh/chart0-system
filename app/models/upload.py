from sqlalchemy import ForeignKey, Date, Column, Float, Integer, String
from .base import Base

class TokyoStock(Base):
    __tablename__ = 'tokyo_stock'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    processing_status = Column(String, nullable=False, default='Processing')
    format = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    user_id = Column(ForeignKey('user.id'), index=True, nullable=False)

    def __repr__(self):
        return f"<TokyoStock(file_name='{self.file_name}', status='{self.processing_status}')>"

class ExportFile(Base):
    __tablename__ = 'export_file'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    processing_status = Column(String, nullable=False, default='Processing')
    format = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    symbol_id = Column(ForeignKey('symbol.id'), index=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    language = Column(String, nullable=False, default="en")
    user_id = Column(ForeignKey('user.id'), index=True, nullable=False)

    def __repr__(self):
        return f"<ExportFile(file_name='{self.file_name}', status='{self.processing_status}')>"