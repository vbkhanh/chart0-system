from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Query
from fastapi.security import HTTPAuthorizationCredentials
from azure.storage.blob.aio import BlobServiceClient
from app.configs.db import get_session
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.snapshot import Snapshot 
from app.utils import get_current_user
from app.schemas import snapshot_schemas
from app.settings import settings
from app.utils import get_blob_sas_token
from app.constants import SNAPSHOT_BLOB_CONTAINER, GENERAL_SNAPSHOT_URL


router = APIRouter(
    prefix="/snapshots"
)

@router.get("", response_model=list[snapshot_schemas.SnapshotOut])
async def get_snapshots(
    session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):  
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        snapshots = await session.scalars(select(Snapshot).where(Snapshot.user_id==current_user.id).order_by(Snapshot.created_at.desc()))
        snapshots = snapshots.all()
        
        for snapshot in snapshots:
            blob_name = f"{snapshot.id}" + "_" + snapshot.title
            new_token = get_blob_sas_token(SNAPSHOT_BLOB_CONTAINER, blob_name)
            snapshot.url += f"?{new_token}"

    finally:
        await session.close()
    
    return snapshots

@router.post("", response_model=None)
async def upload_snapshot(
    file: UploadFile, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        file_name = file.filename
        
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        
        new_snapshot = Snapshot(url=GENERAL_SNAPSHOT_URL, user_id=current_user.id, title=file_name)

        session.add(new_snapshot)
        await session.commit()

        new_snapshot.url += f"{new_snapshot.id}" + "_" + file_name
        await session.commit()

        file_name = f"{new_snapshot.id}" + "_" + file_name

        async with blob_service_client:
            try:
                snapshot_container_client = blob_service_client.get_container_client(SNAPSHOT_BLOB_CONTAINER)
                blob_client = snapshot_container_client.get_blob_client(file_name)
                file_content = await file.read()
                result = await blob_client.upload_blob(file_content, overwrite=True)
            except Exception as e:
                print(f"upload_snapshot_failed: {e}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="upload_snapshot_failed")

    finally:
        await session.close()

    return {"message": "upload_snapshot_successfully"}


@router.patch("/{id}", response_model=None)
async def update_snapshot(
    id: int, file: UploadFile, session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        snapshot = await session.execute(select(Snapshot.id, Snapshot.title).where(Snapshot.id==id).where(Snapshot.user_id==current_user.id))
        snapshot = snapshot.first()

        if snapshot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshot_not_found")
        
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        
        file_name = f"{snapshot.id}" + "_" + snapshot.title
        
        async with blob_service_client:
            try:
                snapshot_container_client = blob_service_client.get_container_client(SNAPSHOT_BLOB_CONTAINER)
                blob_client = snapshot_container_client.get_blob_client(file_name)
                file_content = await file.read()
                result = await blob_client.upload_blob(file_content, overwrite=True)
            except Exception as e:
                print(f"update_snapshot_failed: {e}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="update_snapshot_failed")
            
    finally:
        await session.close()
    
    return {"message": "update_snapshot_successfully"}


@router.delete("/multiple_deletions", response_model=None)
async def delete_snapshots(
    ids: list[int] = Query(), session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        
        snapshots = await session.execute(select(Snapshot.id, Snapshot.title).where(Snapshot.id.in_(ids)).where(Snapshot.user_id==current_user.id))
        snapshots = snapshots.all()
        
        if not snapshots:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshots_not_found")
        
        snapshot_file_names = [f"{snapshot.id}" + "_" + snapshot.title for snapshot in snapshots]

        snapshot_ids = [snapshot.id for snapshot in snapshots]
                
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)

        async with blob_service_client:
            try:
                result = await session.execute(delete(Snapshot).where(Snapshot.id.in_(snapshot_ids)))
                await session.commit()
                snapshot_container_client = blob_service_client.get_container_client(SNAPSHOT_BLOB_CONTAINER)

                # Possibly add codes to check if the blobs exist before deleting them

                result = await snapshot_container_client.delete_blobs(*snapshot_file_names)
            except Exception as e:
                print(f"delete_snapshots_failed: {e}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delete_snapshots_failed")
        
    finally:
        await session.close()

    return {"message": "delete_snapshots_successfully"}

@router.delete("/{id}", response_model=None)
async def delete_snapshot(
    id: int, session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        snapshot = await session.execute(select(Snapshot.id, Snapshot.title).where(Snapshot.id==id).where(Snapshot.user_id==current_user.id))
        snapshot = snapshot.first()

        if snapshot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshot_not_found")
        
        file_name = f"{snapshot.id}" + "_" + snapshot.title
        
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)

        async with blob_service_client:
            try:
                result = await session.execute(delete(Snapshot).where(Snapshot.id==id))
                await session.commit()
                blob_client = blob_service_client.get_blob_client(container=SNAPSHOT_BLOB_CONTAINER, blob=file_name)
                exists = await blob_client.exists()
                if exists:
                    result = await blob_client.delete_blob(delete_snapshots="include")
            except Exception as e:
                print(f"delete_snapshot_failed: {e}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delete_snapshot_failed")
        
    finally:
        await session.close()

    return {"message": "delete_snapshot_successfully"}
