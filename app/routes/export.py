import datetime
from typing import List, Optional
import pandas as pd
from io import BytesIO
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Query
from fastapi.security import HTTPAuthorizationCredentials
from azure.storage.blob.aio import BlobServiceClient
from app.configs.db import get_session
from app.models import TokyoStock, ExportFile, Symbol
from app.utils import get_current_admin
from celery_task.celery_app import celery_app
from app.settings import settings
from app.utils import get_blob_sas_token
from app.schemas.tokyo_stock_schemas import DeleteFilesRequest, ExportFileRequest, SearchExportFileResponse
from app.constants import TOKYO_STOCK_BLOB_CONTAINER, GENERAL_TOKYO_STOCK_URL

pd.options.display.unicode.east_asian_width = True

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=""
)

@router.post("/export", response_model=None)
async def export_bar_data(
    payload: ExportFileRequest,
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    try:
        # Check if file with same name and symbol already exists
        query = select(ExportFile).where(
            ExportFile.file_name == payload.file_name
        )
        result = await session.execute(query)
        existing_file = result.scalar_one_or_none()

        if not existing_file:
            new_file = ExportFile(
                file_name=payload.file_name,
                processing_status="Processing",
                format=payload.format,
                symbol_id=payload.symbol_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                language=payload.language,
                user_id=current_user.id
            )
            session.add(new_file)
            await session.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_name_already_exists"
            )

        celery_app.send_task(
            "export_bar_data",
            args=[
                payload.model_dump()
            ], queue=settings.CELERY_TOKYO_STOCK_QUEUE,
        )

        return {
            "message": "export_task_initiated"
        }
    finally:
        await session.close()

@router.post("/re-export", response_model=None)
async def re_export_bar_data(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    try:
        # Retrieve the existing file record
        query = select(ExportFile).where(
            ExportFile.id == file_id,
            ExportFile.user_id == current_user.id
        )
        result = await session.execute(query)
        existing_file = result.scalar_one_or_none()

        if not existing_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file_not_found"
            )

        # Update the processing status to "Processing"
        existing_file.processing_status = "Processing"
        await session.commit()

        # Prepare payload for re-export
        payload = ExportFileRequest(
            symbol_id=existing_file.symbol_id,
            start_date=existing_file.start_date,
            end_date=existing_file.end_date,
            format=existing_file.format,
            file_name=existing_file.file_name,
            language=existing_file.language  # Assuming default language is English
        )

        celery_app.send_task(
            "export_bar_data",
            args=[
                payload.model_dump()
            ], queue=settings.CELERY_TOKYO_STOCK_QUEUE,
        )

        return {
            "message": "re_export_task_initiated"
        }
    finally:
        await session.close()

@router.get("/export", response_model=SearchExportFileResponse)
async def search_export_files(
    file_name: Optional[str] = Query(None),
    symbol_name: Optional[str] = Query(None), 
    status: Optional[str] = Query(None),
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    page_size: Optional[int] = Query(None),
    page: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
):
    try:
        query = select(ExportFile, Symbol.name).join(Symbol).where(ExportFile.user_id == current_user.id)
        
        if file_name:
            query = query.where(ExportFile.file_name.ilike(f"%{file_name}%"))
        if symbol_name:
            query = query.where(Symbol.name.ilike(f"%{symbol_name}%"))
        if status:
            query = query.where(ExportFile.processing_status.ilike(f"%{status}%"))
        if start_date and end_date:
            query = query.where(ExportFile.start_date >= start_date, ExportFile.end_date <= end_date)

        total_items_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total_items = total_items_result.scalar_one()

        if page and page_size:
            query = query.offset((page - 1) * page_size).limit(page_size)

        query = query.order_by(ExportFile.created_at.desc())
        result = await session.execute(query)
        files = result.fetchall()

        files_list = []
        for file, symbol_name in files:
            file_dict = file.__dict__
            file_dict["symbol_name"] = symbol_name
            if file_dict["processing_status"].lower() != "failed":
                new_token = get_blob_sas_token(TOKYO_STOCK_BLOB_CONTAINER, file_dict["file_name"])
                file_dict["url"] = f'{GENERAL_TOKYO_STOCK_URL}{file_dict["file_name"]}?{new_token}'
            else:
                file_dict["url"] = None
            files_list.append(file_dict)

        return {"total_items": total_items, "data": files_list}
    finally:
        await session.close()

@router.delete("/export", response_model=dict)
async def delete_export_file(
    file_ids: DeleteFilesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict:
    try:
        # Get files to delete
        query = select(ExportFile).where(
            ExportFile.id.in_(file_ids.file_ids),
            ExportFile.user_id == current_user.id
        )
        result = await session.execute(query)
        files = result.scalars().all()

        if not files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="no_files_found"
            )

        # Delete from database
        for file in files:
            await session.delete(file)
        await session.commit()

        # Delete from blob storage
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(TOKYO_STOCK_BLOB_CONTAINER)
        
        for file in files:
            try:
                blob_client = container_client.get_blob_client(file.file_name)
                await blob_client.delete_blob()
            except Exception as e:
                logger.error(f"Failed to delete file {file.file_name} from blob storage: {str(e)}")

        return {
            "message": "deleted_file"
        }
    finally:
        await session.close()
