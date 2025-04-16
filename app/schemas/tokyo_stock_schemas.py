from typing import List, Optional, Literal

from pydantic import BaseModel
from datetime import datetime, date

class TokyoStockSchema(BaseModel):
    id: int
    file_name: str
    processing_status: str
    created_at: datetime
    format: str
    user_id: int
    file_size: Optional[int]
    class Config:
        from_attributes = True

class SearchFileResponseSchema(TokyoStockSchema):
    url: Optional[str]

class SearchFileResponse(BaseModel):
    data: List[SearchFileResponseSchema]
    total_items: int

class ExportFileSchema(TokyoStockSchema):
    symbol_id: int
    symbol_name: str
    start_date: date
    end_date: date

class SearchExportFileResponseSchema(ExportFileSchema):
    url: Optional[str]

class SearchExportFileResponse(BaseModel):
    data: List[SearchExportFileResponseSchema]
    total_items: int

class DeleteFilesRequest(BaseModel):
    file_ids: List[int]

class ExportFileRequest(BaseModel):
    symbol_id: int
    start_date: date
    end_date: date
    format: Literal["csv", "xlsx"]
    file_name: str
    language: Literal["jp", "en"]
