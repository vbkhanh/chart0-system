from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.configs.db import get_session
from app.schemas import watchlist_schemas
from app.models.watchlist import Watchlist
from app.models import Bar, Symbol, Tick
from app.utils import get_current_user
from datetime import timedelta
import logging


router = APIRouter(
    prefix="/watchlists"
)

logger = logging.getLogger(__name__)


@router.get("", response_model=list[watchlist_schemas.WatchlistOut])
async def get_watchlists(session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        watchlists = await session.execute(select(Watchlist.id, Watchlist.title, Watchlist.sections).where(Watchlist.user_id==current_user.id))
    finally:
        await session.close()
  
    return watchlists.all()

@router.get("/bars", response_model=list[watchlist_schemas.WatchListBarOut])
async def get_latest_bars(symbol_ids: str, session: AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        symbol_id_list = [int(id.strip()) for id in symbol_ids.split(",")]

        latest_time_subquery = (
            select(
                Bar.symbol_id,
                func.max(Bar.from_time).label("latest")
            )
            .where(Bar.symbol_id.in_(symbol_id_list), Bar.type == '1d')
            .group_by(Bar.symbol_id)
            .subquery()
        )

        latest_bar_data = await session.execute(
            select(
                Bar.symbol_id,
                Bar.type,
                Bar.from_time,
                Bar.high,
                Bar.low,
                Bar.close.label("price"),
            )
            .join(
                latest_time_subquery,
                (Bar.symbol_id == latest_time_subquery.c.symbol_id) &
                (Bar.from_time == latest_time_subquery.c.latest)
            )
        )

        previous_day_subquery = (
            select(
                Bar.symbol_id,
                func.max(Bar.from_time).label("previous")
            )
            .join(
                latest_time_subquery,
                (Bar.symbol_id == latest_time_subquery.c.symbol_id) &
                (Bar.from_time < latest_time_subquery.c.latest)
            )
            .where(Bar.type == '1d')
            .group_by(Bar.symbol_id)
            .subquery()
        )

        previous_day_bars = await session.execute(
            select(
                Bar.symbol_id,
                Bar.type,
                Bar.from_time,
                Bar.close.label("price")
            )
            .join(
                previous_day_subquery,
                (Bar.symbol_id == previous_day_subquery.c.symbol_id) &
                (Bar.from_time == previous_day_subquery.c.previous)
            ).where(Bar.type=='1d')
        )

        previous_bars_data = {bar.symbol_id: bar for bar in previous_day_bars.all()}
        latest_bar_data = latest_bar_data.all()

        result_data = []
        for bar in latest_bar_data:
            previous_bar = previous_bars_data.get(bar.symbol_id)
            if previous_bar:
                change = bar.price - previous_bar.price
                change_percentage = (change / previous_bar.price) * 100 if previous_bar.price != 0 else 0

                result_data.append({
                    "symbol_id": bar.symbol_id,
                    "price": bar.price,
                    "previous_close": previous_bar.price,
                    "change": change,
                    "change_percentage": change_percentage
                })
        
        latest_tick_time_subquery = (
            select(
                Tick.symbol_id,
                func.max(Tick.datetime_msc).label("datetime_msc")
            )
            .where(Tick.symbol_id.in_(symbol_id_list))
            .group_by(Tick.symbol_id)
            .subquery()
        )

        latest_ticks = await session.execute(
            select(
                Tick.symbol_id,
                Tick.datetime_msc.label("latest_tick"),
                Tick.ask.label("latest_price")
            )
            .join(
                latest_tick_time_subquery,
                (Tick.symbol_id == latest_tick_time_subquery.c.symbol_id) &
                (Tick.datetime_msc == latest_tick_time_subquery.c.datetime_msc)
            )
        )

        previous_tick_time_subquery = (
            select(
                Tick.symbol_id,
                func.max(Tick.datetime_msc).label("previous_datetime_msc")
            )
            .where(Tick.symbol_id.in_(symbol_id_list))
            .where(Tick.datetime_msc < latest_tick_time_subquery.c.datetime_msc)
            .group_by(Tick.symbol_id)
            .subquery()
        )

        previous_ticks = await session.execute(
            select(
                Tick.symbol_id,
                Tick.datetime_msc.label("previous_tick"),
                Tick.ask.label("previous_price")
            )
            .join(
                previous_tick_time_subquery,
                (Tick.symbol_id == previous_tick_time_subquery.c.symbol_id) &
                (Tick.datetime_msc == previous_tick_time_subquery.c.previous_datetime_msc)
            )
        )

        
        previous_tick_data = {tick.symbol_id: tick for tick in previous_ticks.all()}
        latest_tick_data = {tick.symbol_id: tick for tick in latest_ticks.all()}

        res = []
        for record in result_data:
            if  latest_tick_data.get(record["symbol_id"]):
                record["price"] = latest_tick_data[record["symbol_id"]].latest_price
                record["change"] = record["price"] - record["previous_close"]
                record["change_percentage"] = (change / record["previous_close"]) * 100 if record["previous_close"] != 0 else 0
                if previous_tick_data.get(record["symbol_id"]):
                    if latest_tick_data[record["symbol_id"]].latest_price > previous_tick_data[record["symbol_id"]].previous_price:
                        record["compare_to_previous_tick"] = True
                    else:
                        record["compare_to_previous_tick"] = False
            res.append(record)

        return res
    finally:
        await session.close()



@router.post("", response_model=None)
async def create_watchlist(watchlist:watchlist_schemas.WatchlistIn, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        new_watchlist = Watchlist(title=watchlist.title, sections=watchlist.sections, user_id=current_user.id)

        session.add(new_watchlist)

        await session.commit()
    finally:
        await session.close()

    return {"message": "successfully_create_watchlist"}


@router.patch("/{watchlist_id}", response_model=None)   
async def edit_watchlist(watchlist_id:int, watchlist:watchlist_schemas.WatchlistIn, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        existing_watchlist_id = await session.scalars(select(Watchlist.id).where(Watchlist.id==watchlist_id).where(Watchlist.user_id==current_user.id))
        existing_watchlist_id = existing_watchlist_id.first()

        if existing_watchlist_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist_not_found")
        
        try:
            result = await session.execute(update(Watchlist).where(Watchlist.id==watchlist_id).values(
                title = watchlist.title,
                sections = watchlist.sections
            ))
            await session.commit()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"error_editing_watchlist: {e}")
    finally:
        await session.close()
    
    return {"message": "successfully_edit_watchlist"}


@router.delete("/{watchlist_id}", response_model=None)
async def delete_watchlist(watchlist_id:int, session:AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)) -> dict[str, str]:
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        existing_watchlist_id = await session.scalars(select(Watchlist.id).where(Watchlist.id==watchlist_id).where(Watchlist.user_id==current_user.id))
        existing_watchlist_id = existing_watchlist_id.first()

        if existing_watchlist_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist_not_found")

        try:
            result = await session.execute(delete(Watchlist).where(Watchlist.id==watchlist_id))
            await session.commit()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"error_deleting_watchlist: {e}")
    finally:
        await session.close()
    
    return {"message": "successfully_delete_watchlist"}
