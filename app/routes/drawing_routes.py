from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from app.configs.db import get_session
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.drawing import Drawing
from app.utils import get_current_user
from app.schemas import drawing_schemas

router = APIRouter(
    prefix="/drawings"
)

@router.get("", response_model=list[drawing_schemas.DrawingOut])
async def get_drawings(
    session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        drawings = await session.execute(select(Drawing.id, Drawing.data, Drawing.symbol_id).where(Drawing.user_id==current_user.id))
        drawings = drawings.all()

    finally:
        await session.close()

    return drawings

@router.get("/by_symbol", response_model=list[drawing_schemas.DrawingOut])
async def get_drawings_by_symbol(
    symbol_id: int, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        drawings = await session.execute(select(Drawing.id, Drawing.data, Drawing.symbol_id).where(Drawing.user_id==current_user.id).where(Drawing.symbol_id==symbol_id))
        drawings = drawings.all()

    finally:
        await session.close()

    return drawings 

@router.post("", response_model=None)
async def create_drawing(
    drawing: drawing_schemas.DrawingIn, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        new_drawing = Drawing(user_id=current_user.id, symbol_id=drawing.symbol_id, data=drawing.data)
        
        session.add(new_drawing)

        await session.commit()

    finally:
        await session.close()

    return { "message": "success" }
    


@router.patch("/{id}", response_model=None)
async def update_drawing(
    id: int, drawing_data: drawing_schemas.DrawingData, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        existing_drawing_id = await session.scalars(select(Drawing.id).where(Drawing.id == id).where(Drawing.user_id==current_user.id))

        existing_drawing_id = existing_drawing_id.first()

        if existing_drawing_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drawing_not_exist")
        
        result = await session.execute(update(Drawing).where(Drawing.id==id).values(data=drawing_data.data))
        await session.commit()
    
    except Exception as e:
        print(f"error_updating_drawing: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_updating_drawing")
    finally:
        await session.close()

    return { "message": "success" }

@router.delete("/{id}", response_model=None)
async def delete_drawing(
    id: int, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        existing_drawing_id = await session.scalars(select(Drawing.id).where(Drawing.id == id).where(Drawing.user_id==current_user.id))

        existing_drawing_id = existing_drawing_id.first()

        if existing_drawing_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drawing_not_exist")
        
        result = await session.execute(delete(Drawing).where(Drawing.id==id))
        await session.commit()
    
    except Exception as e:
        print(f"error_updating_drawing: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_deleting_drawing")
    finally:
        await session.close()

    return { "message": "success" }