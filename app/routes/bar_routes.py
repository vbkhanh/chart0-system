from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.configs.db import get_session
from sqlalchemy import select, func, and_
from app.models import Bar
from app.utils import get_current_user
from app.schemas import bar_schemas
from datetime import date

router = APIRouter(
    prefix="/bars"
)

@router.get("/earliest_and_latest", response_model=list[dict])
async def get_bar_extremes(
    symbol_ids: str = Query(...),
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")

        # Convert the comma-separated string of symbol_ids into a list of integers
        symbol_id_list = [int(id.strip()) for id in symbol_ids.split(',')]

        extremes = []
        query = select(
            Bar.symbol_id,
            func.min(Bar.from_time).label("earliest"),
            func.max(Bar.to_time).label("latest")
        ).where(
            Bar.symbol_id.in_(symbol_id_list)
        ).group_by(
            Bar.symbol_id
        )

        result = await session.execute(query)
        extremes = [
            {
                "symbol_id": row.symbol_id,
                "earliest": row.earliest,
                "latest": row.latest
            }
            for row in result
        ]

        return extremes
    finally:
        await session.close()


@router.get("", response_model=list[bar_schemas.BarOut])
async def get_bars(
    symbol_id:int, bar_type:str, from_time:date | None = None, to_time: date | None = None, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> list[Bar]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        query = select( Bar.from_time, 
                        Bar.to_time, 
                        Bar.open, 
                        Bar.high, 
                        Bar.low, 
                        Bar.close, 
                        Bar.provisional_open, 
                        Bar.provisional_close
                    ).where(Bar.symbol_id==symbol_id).where(Bar.type==bar_type)
        
        if from_time is not None and to_time is not None:
            query = query.where(Bar.from_time.between(from_time, to_time), Bar.to_time.between(from_time, to_time))
        
        query = query.order_by(Bar.from_time.asc())

        bars = await session.execute(query)

        bars = bars.all()

    finally:
        await session.close()
    
    return bars

@router.get("/previous_day_prices", response_model=list[bar_schemas.BarPreviousDayPricesOut])
async def get_previous_day_prices(
    session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        sbq = select(Bar.symbol_id.label("symbol_id"), func.max(Bar.from_time).label("previous_day")).group_by(Bar.symbol_id).subquery()

        previous_day_prices = await session.execute(
            select(Bar.symbol_id, Bar.close, Bar.high, Bar.low).select_from(Bar).join(sbq, and_(Bar.symbol_id == sbq.c.symbol_id, Bar.from_time == sbq.c.previous_day)).where(Bar.type == "1d")
        )

        previous_day_prices = previous_day_prices.all()

    finally:
        await session.close()

    return previous_day_prices
