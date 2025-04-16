from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials
from app.configs.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils import get_current_user
from app.controller import ma_calculator
from app.constants import BAR_TYPES, PERIOD_LIST
from sqlalchemy import select, update, func
from app.models.ma_list import MA_List, MA_Line_Point, MA_Lines_Intersection_Point
from app.models.ma_lines_intersection import MA_Lines_Intersection
from app.models import Symbol, Bar, Tick
from app.schemas import ma_list_schemas
from app.schemas import symbol_schemas
from datetime import date, datetime, timedelta

from celery_task.celery_app import celery_app
from celery.result import AsyncResult

import logging
from app.settings import settings
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/indicators"
)

@router.get("/MA", response_model=ma_list_schemas.MA_ListOut)
async def calculate_MA(
    symbol_id: int, bar_type: str, period: int, start_date: date = Query(None), end_date: date = Query(None), session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not enabled")
        
        query = select(
            MA_Line_Point.date, MA_Line_Point.price.label("value")
        ).filter(MA_Line_Point.symbol_id == symbol_id, MA_Line_Point.period == period, MA_Line_Point.bar_type == bar_type)
        
        if start_date and end_date:
            query = query.filter(MA_Line_Point.date >= start_date, MA_Line_Point.date <= end_date)
        ma_list_points = await session.execute(query)
        ma_list_points = ma_list_points.all()
        
        if not ma_list_points:
            if start_date:
                start_date = start_date - timedelta(period)
            ma_list_points = await ma_calculator.calculate_ma_list_v2(session, period, symbol_id, bar_type, start_date, end_date)
            for point in ma_list_points:
                ma_line_point = MA_Line_Point(symbol_id=symbol_id, bar_type=bar_type, period=period, date=point['date'], price=point['value'])
                session.add(ma_line_point)
            await session.commit()
    finally:
        await session.close()

    return {
        "points": ma_list_points
    }

@router.get("/MA_v2", response_model=ma_list_schemas.MA_ListOutV2)
async def calculate_MA(
    symbol_id: int, bar_type: str, start_date: date = Query(None), end_date: date = Query(None), session: AsyncSession = Depends(get_session),
    current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not enabled")
        
        res = {}
        for period in PERIOD_LIST:
            query = select(
                MA_Line_Point.date, MA_Line_Point.price.label("value")
            ).filter(MA_Line_Point.symbol_id == symbol_id, MA_Line_Point.period == period, MA_Line_Point.bar_type == bar_type)
            
            if start_date and end_date:
                query = query.filter(MA_Line_Point.date >= start_date, MA_Line_Point.date <= end_date)
            ma_list_points = await session.execute(query)
            ma_list_points = ma_list_points.all()
            
            if not ma_list_points:
                if start_date:
                    start_date = start_date - timedelta(period)
                ma_list_points = await ma_calculator.calculate_ma_list_v2(session, period, symbol_id, bar_type, start_date, end_date)
                for point in ma_list_points:
                    ma_line_point = MA_Line_Point(symbol_id=symbol_id, bar_type=bar_type, period=period, date=point['date'], price=point['value'])
                    session.add(ma_line_point)
                await session.commit()
            res[f"MA_{period}"] = ma_list_points
    finally:
        await session.close()

    return res

@router.get("/intersections", response_model=list[symbol_schemas.MAIntersectionSymbolOut])
async def list_symbols_with_intersections(
    ma1_period: int, ma2_period: int, bar_type: str, date_range: list[date] = Query(None), category: str = None,
    page: int = None, page_size: int = None, symbol_search: str = None,
    session: AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    try:
        if current_user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_approved")
        if current_user.state != "enabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_enabled")
        
        if bar_type not in BAR_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_bar_type")
        
        if ma1_period not in PERIOD_LIST or ma2_period not in PERIOD_LIST:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_period")
        
        if ma1_period == ma2_period:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="periods_must_be_different")
         
        if ma1_period > ma2_period:
            ma1_period, ma2_period = ma2_period, ma1_period

        query = select(
            Symbol.id.label("symbol_id"), 
            Symbol.name,
            Symbol.japanese_name,
            Symbol.symbol_info, 
            Symbol.description, 
            Symbol.category
        ).select_from(Symbol).join(
            MA_Lines_Intersection_Point, 
            MA_Lines_Intersection_Point.symbol_id == Symbol.id
        ).where(
            MA_Lines_Intersection_Point.bar_type == bar_type, 
            MA_Lines_Intersection_Point.line1_period == ma1_period, 
            MA_Lines_Intersection_Point.line2_period == ma2_period
        ).group_by(
            Symbol.id
        )

        if date_range is not None:
            start_date = date_range[0]
            end_date = date_range[1]
            query = query.where(
                MA_Lines_Intersection_Point.date >= start_date,
                MA_Lines_Intersection_Point.date <= end_date
            )

        if category:
            query = query.where(Symbol.category == category)

        if symbol_search:
            query = query.where(
                (Symbol.name.ilike(f"%{symbol_search}%")) |
                (Symbol.code.ilike(f"%{symbol_search}%")) |
                (Symbol.description.ilike(f"%{symbol_search}%")) |
                (Symbol.japanese_name.ilike(f"%{symbol_search}%"))
            )

        if page is not None and page_size is not None:
            query = query.offset((page - 1) * page_size).limit(page_size)
        symbols = await session.execute(query)
        symbols = symbols.all()
    finally:
        await session.close()

    return symbols

@router.get("/intersections/bar", response_model=list[symbol_schemas.MAIntersectionBarOut])
async def get_intersections_bar(
    symbol_ids: str, session: AsyncSession = Depends(get_session), current_user: HTTPAuthorizationCredentials = Depends(get_current_user)
):
    """
    Endpoint to get low, high, close, change, and change_percentage for given symbol_ids.
    """
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
                    "high": bar.high,
                    "low": bar.low,
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
@router.get("/calculate_ma_task")
async def trigger_calculate_ma_task(
    task_name: str = Query("calculate_MA_task", description="Name of the task to trigger"),
    args: list = Query(None, description="Arguments for the task")
):
    """
    Endpoint to trigger the calculate_MA_task in Celery.
    """
    task = celery_app.send_task(task_name, args=args)
    return {"task_id": task.id, "status": "Task has been triggered"}

@router.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    """
    Endpoint to get the status of a Celery task.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    return {"task_id": task_id, "status": task_result.status, "result": task_result.result}
