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
from app.schemas.tokyo_stock_schemas import DeleteFilesRequest, SearchFileResponse, ExportFileRequest, SearchExportFileResponse
from app.constants import TOKYO_STOCK_BLOB_CONTAINER, TOKYO_STOCK_MAPPING, GENERAL_TOKYO_STOCK_URL

pd.options.display.unicode.east_asian_width = True

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tokyo_stock"
)

@router.post("/upload", response_model=None)
async def upload_tokyo_stock(
    files: List[UploadFile], session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload more than 5 files at a time."
        )

    total_size = sum(file.size for file in files)
    if total_size > 10 * 1024 * 1024:  # 10 MB in bytes
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total size of files exceeds the maximum allowed size of 10MB."
        )

    results = []
    for file in files:
        try:
            if file.content_type == 'text/csv':
                file_format = 'csv'
            elif file.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                file_format = 'excel'
            else:
                raise Exception("Unsupported file format")
            
            file_content = await file.read()

            # Read the file content into a DataFrame
            if file_format == 'csv':
                df = pd.read_csv(BytesIO(file_content), encoding="shift_jis")
            elif file_format == 'excel':
                df = pd.read_excel(BytesIO(file_content))
                
            # Check if all required columns are present
            missing_columns = [col for col in TOKYO_STOCK_MAPPING.values() if col not in df.columns]
            if missing_columns:
                raise Exception(f"Missing required columns: {', '.join(missing_columns)}")

            file_name = file.filename
            file_name_parts = file_name.split('.', 1)
            file_extension = file_name_parts[-1]
            file_name = ".".join(file_name_parts[:-1])
            file_name = f'{file_name}-{datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.{file_extension}'
            
            blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
            async with blob_service_client:
                container_client = blob_service_client.get_container_client(TOKYO_STOCK_BLOB_CONTAINER)
                blob_client = container_client.get_blob_client(file_name)
                result = await blob_client.upload_blob(file_content, overwrite=True)

            new_tokyo_stock = TokyoStock(
                file_name=file_name,
                processing_status="Processing",
                created_at=datetime.datetime.now(),
                format=file_format,
                user_id=current_user.id,
                file_size=file.size
            )
            session.add(new_tokyo_stock)
            await session.commit()
            await session.refresh(new_tokyo_stock)

            celery_app.send_task("process_tokyo_stock_file", args=[file_name, file_format, new_tokyo_stock.id], queue=settings.CELERY_TOKYO_STOCK_QUEUE,)
            results.append({"file_name": file.filename, "status": "Processing", "detail": "Upload Successfully", "file_id": new_tokyo_stock.id})
        except Exception as e:
            logger.error(f"Error uploading file {file.filename}: {e}")
            results.append({"file_name": file.filename, "status": "Failed", "detail": "error_uploading_file"})
        finally:
            await session.close()

    return {"results": results}


@router.get("/search", response_model=SearchFileResponse)
async def search_tokyo_stock(
    file_ids: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    page_size: Optional[int] = Query(None),
    page: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
):
    try:
        tokyo_stock_id = [int(id.strip()) for id in file_ids.split(',')] if file_ids else []
        query = select(TokyoStock).where(TokyoStock.user_id == current_user.id)
        
        if tokyo_stock_id:
            query = query.where(TokyoStock.id.in_(tokyo_stock_id))
        if name:
            query = query.where(TokyoStock.file_name.ilike(f"%{name}%"))
        if status:
            query = query.where(TokyoStock.processing_status.ilike(f"%{status}%"))
        if start_date and end_date:
            start_date = datetime.datetime.combine(start_date, datetime.time.min)
            end_date = datetime.datetime.combine(end_date, datetime.time.max)
            query = query.where(TokyoStock.created_at.between(start_date, end_date))

        total_items_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total_items = total_items_result.scalar_one()
        
        if page and page_size:
            query = query.offset((page - 1) * page_size).limit(page_size)
        
        query = query.order_by(TokyoStock.file_name.asc())
        result = await session.execute(query)
        tokyo_stocks = [tokyo_stock.__dict__ for tokyo_stock in result.scalars().all()]

        for tokyo_stock in tokyo_stocks:
            new_token = get_blob_sas_token(TOKYO_STOCK_BLOB_CONTAINER, tokyo_stock["file_name"])
            tokyo_stock["url"] = f'{GENERAL_TOKYO_STOCK_URL}{tokyo_stock["file_name"]}?{new_token}'
        
        return {"total_items": total_items, "data": tokyo_stocks}
    except Exception as e:
        logger.error(f"Error searching Tokyo Stock: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_searching_tokyo_stock")
    
    finally:
        await session.close()

@router.delete("/delete", response_model=None)
async def delete_tokyo_stock(
    file_ids: DeleteFilesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    try:
        for id in file_ids.file_ids:
            # Check if the file exists
            query = select(TokyoStock).where(TokyoStock.id == id, TokyoStock.user_id == current_user.id)
            result = await session.execute(query)
            tokyo_stock = result.scalar_one_or_none()

            if tokyo_stock:
                # Call the Celery task to clean up data in the database and Azure Blob Storage
                celery_app.send_task("cleanup_tokyo_stock_data", args=[tokyo_stock.id, tokyo_stock.file_name], queue=settings.CELERY_TOKYO_STOCK_QUEUE,)

        return {"status": "Success", "detail": "File deletion initiated for all specified files."}
    except Exception as e:
        logger.error(f"Error deleting Tokyo Stock files: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_deleting_tokyo_stock")
    finally:
        await session.close()


@router.delete("/delete_all", response_model=None)
async def delete_all_tokyo_stocks(
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_admin)
) -> dict[str, str]:
    try:
        # Fetch all TokyoStock records for the current user
        query = select(TokyoStock).where(TokyoStock.user_id == current_user.id)
        result = await session.execute(query)
        tokyo_stocks = result.scalars().all()

        for tokyo_stock in tokyo_stocks:
            # Call the Celery task to clean up data in the database and Azure Blob Storage
            celery_app.send_task("cleanup_tokyo_stock_data", args=[tokyo_stock.id, tokyo_stock.file_name], queue=settings.CELERY_TOKYO_STOCK_QUEUE,)

        return {"status": "Success", "detail": "File deletion initiated for all files."}
    except Exception as e:
        logger.error(f"Error deleting all Tokyo Stock files: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_deleting_all_tokyo_stock")
    finally:
        await session.close()
