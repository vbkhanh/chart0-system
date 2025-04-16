from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated
from fastapi.security import HTTPAuthorizationCredentials
from app.configs.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models import Tick
from typing import Annotated
from app.utils import get_current_user
from datetime import datetime
from app.schemas import tick_schemas

router = APIRouter(
    prefix="/ticks"
)

@router.get("", response_model=list[tick_schemas.TickOut])
async def get_ticks(
    symbol_id:int, session:AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user),
    offset:int = 0, limit: Annotated[int, Query(le=1000)] = 1000
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        ticks = await session.execute(select(Tick.bid, Tick.ask, Tick.datetime_msc).where(Tick.symbol_id==symbol_id).offset(offset).limit(limit))
        ticks = ticks.all()

    finally:
        await session.close()

    return ticks

@router.get("/latest", response_model=list[tick_schemas.LatestTickOut])
async def get_latest_tick(
    session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        sbq = select(Tick.symbol_id.label("symbol_id"), func.max(Tick.datetime_msc).label("previous_datetime")).group_by(Tick.symbol_id).subquery()
        
        latest_ticks = await session.execute(
            select(Tick.symbol_id, Tick.ask).select_from(Tick).join(sbq, and_(Tick.symbol_id == sbq.c.symbol_id, Tick.datetime_msc == sbq.c.previous_datetime))
        )

        latest_ticks = latest_ticks.all()

    finally:
        await session.close()

    return latest_ticks

@router.get("/highest_and_lowest", response_model=None)
async def get_today_min_max_tick(
    symbol_ids: str, session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
) -> dict[str, Tick]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        start_of_day = int(datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()*1000)
        end_of_day = int(datetime.now().timestamp()*1000)
        
        symbol_id_list = [int(symbol_id) for symbol_id in symbol_ids.split(",")]
        min_max_ticks = await session.execute(
            select(
                Tick.symbol_id,
                func.min(Tick.ask).label('min_ask'),
                func.max(Tick.ask).label('max_ask'),
                func.min(Tick.bid).label('min_bid'),
                func.max(Tick.bid).label('max_bid'),
            ).where(
                Tick.symbol_id.in_(symbol_id_list),
                Tick.datetime_msc >= start_of_day,
                Tick.datetime_msc <= end_of_day
            ).group_by(Tick.symbol_id)
        )
        
        results = min_max_ticks.all()
        
        return {
            result.symbol_id: {
                "min_ask": result.min_ask,
                "max_ask": result.max_ask,
                "min_bid": result.min_bid,
                "max_bid": result.max_bid
            } for result in results
        }
    finally:
        await session.close()
