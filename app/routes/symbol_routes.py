from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from app.models.symbol import Symbol
from app.configs.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.schemas import symbol_schemas
from app.utils import get_current_user
import logging
from datetime import date, datetime
from app.constants import TOP_SYMBOLS

router = APIRouter(
    prefix="/symbols"
)

logger = logging.getLogger(__name__)


@router.get("")
async def get_all(
    page: int | None = None,
    page_size: int | None = None,
    search: str | None = None,
    category: str | None = None,
    description: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        query = select(Symbol)
        if category == 'Stock':
            query = query.order_by(
                func.length(Symbol.code).asc(),
                Symbol.code.asc()
            )
        else:
            query = query.order_by(Symbol.name.asc())
        
        if search:
            query = query.where(
                (func.lower(Symbol.name).ilike(f"%{search.lower()}%")) | 
                (func.lower(Symbol.code).ilike(f"%{search.lower()}%")) |
                (func.lower(Symbol.japanese_name).ilike(f"%{search.lower()}%"))
            )
        if description:
            query = query.where(
                (func.lower(Symbol.description).ilike(f"%{description.lower()}%")) |
                (func.lower(Symbol.japanese_name).ilike(f"%{description.lower()}%"))
            )
        if category:
            query = query.where(
                (func.lower(Symbol.category).ilike(f"%{category.lower()}%"))
            )
        if start_date and end_date:
            query = query.where(
                Symbol.created_at.between(
                    datetime.combine(start_date, datetime.min.time()), 
                    datetime.combine(end_date, datetime.max.time())
                )
            )
        
        total_symbols_count_query = await session.execute(select(func.count()).select_from(query.subquery()))
        total_symbols = total_symbols_count_query.scalar_one()
        
        if page and page_size:
            query = query.limit(page_size).offset((page - 1) * page_size)
        paginated_symbols_query = await session.execute(query)
        symbols = paginated_symbols_query.scalars().all()
                
    finally:
        await session.close()

    return {
        "symbols": symbols,
        "total_items": total_symbols
    }

@router.get("/top-symbols")
async def get_top_symbols(
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")

        query = select(Symbol).where(
            func.lower(Symbol.name).in_([name.lower() for name in TOP_SYMBOLS])
        ).order_by(Symbol.name.asc())

        top_symbols_query = await session.execute(query)
        top_symbols = top_symbols_query.scalars().all()

    finally:
        await session.close()

    return top_symbols


@router.get("/{symbol_id}", response_model=symbol_schemas.SymbolOut)
async def get_one(symbol_id:int, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        symbol = await session.scalars(select(Symbol).where(Symbol.id==symbol_id))
    finally:
        await session.close()

    return symbol.first()

@router.patch("/{symbol_id}/category", response_model=None)
async def set_categories(
    symbol_id:int, category:symbol_schemas.CategorySetUp, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        exisitng_symbol_id = await session.scalars(select(Symbol.id).where(Symbol.id == symbol_id))
        
        exisitng_symbol_id = exisitng_symbol_id.first()
        
        if exisitng_symbol_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="symbol_not_found")
        
        try:
            result = await session.execute(update(Symbol).where(Symbol.id==symbol_id).values(category=category.new_category))
            await session.commit()
        except Exception as e:
            logger.error(f"Error while setting categories: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error_setting_categories")    
    finally:
        await session.close()

    return {"message": "successfully_set_category"}
