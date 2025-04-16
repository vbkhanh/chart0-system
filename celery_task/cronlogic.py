from app.controller.ma_calculator import calculate_ma_list_v2, find_intersection
from app.configs.db import get_session
from app.models.symbol import Symbol
from app.models.bar import Bar
from app.models.ma_list import MA_List, MA_Line_Point, MA_Lines_Intersection_Point
from app.models.ma_lines_intersection import MA_Lines_Intersection
from app.constants import PERIOD_LIST, BAR_TYPES, PERIOD_PAIRS
from sqlalchemy import select, update, delete
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio 
import logging 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_all_symbol_ids():
    async for session in get_session():
        try:
            symbol_ids = await session.scalars(select(Symbol.id).order_by(Symbol.id))
            return symbol_ids.all()
        except Exception as e:
            logger.error(f"An error occurred while fetching stock symbol IDs: {e}")
            return []
        finally:
            await session.close()

async def calculate_MA_task(symbol_id: int, start_date: datetime.date = None, end_date: datetime.date = None):
    async for session in get_session():
        try:
            logger.info(f"Processing MA: symbol {symbol_id}")
            if start_date is None:
                start_date = datetime.now().date() - timedelta(1)
            for period in PERIOD_LIST:
                for bar_type in BAR_TYPES:
                    start_date = start_date - timedelta(period)
                    ma_list_points = await calculate_ma_list_v2(session, period, symbol_id, bar_type, start_date=start_date)
                    existing_points = await session.scalars(select(MA_Line_Point).where(
                        MA_Line_Point.symbol_id == symbol_id, 
                        MA_Line_Point.period == period, 
                        MA_Line_Point.bar_type == bar_type, 
                        MA_Line_Point.date >= start_date
                    ))
                    existing_points = existing_points.all()
                    for point in ma_list_points:
                        existing_point = next((ep for ep in existing_points if ep.date == point['date']), None)
                        if existing_point:
                            existing_point.price = point['value']
                        else:
                            new_point = MA_Line_Point(symbol_id=symbol_id, bar_type=bar_type, period=period, date=point['date'], price=point['value'])
                            session.add(new_point)
                    await session.commit()
        except Exception as e:
            logger.info(f"An error occurred: {e}")
        finally:
            await session.close()
        return

async def find_intersection_task(symbol_id: int, start_date: datetime.date = None, end_date: datetime.date = None):
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            async for session in get_session():
                try:
                    if start_date is None:
                        start_date = datetime.now().date() - timedelta(3)

                    logger.info(f"Finding intersections for symbol {symbol_id} starting from {start_date}")
                    
                    for bar_type in BAR_TYPES:
                        
                        for ma1_period, ma2_period in PERIOD_PAIRS:
                            
                            ma1_points = await session.scalars(select(MA_Line_Point).where(
                                MA_Line_Point.symbol_id == symbol_id, 
                                MA_Line_Point.period == ma1_period, 
                                MA_Line_Point.bar_type == bar_type,
                                MA_Line_Point.date >= start_date
                            ))
                            ma2_points = await session.scalars(select(MA_Line_Point).where(
                                MA_Line_Point.symbol_id == symbol_id, 
                                MA_Line_Point.period == ma2_period, 
                                MA_Line_Point.bar_type == bar_type,
                                MA_Line_Point.date >= start_date
                            ))
                            
                            ma1_points = ma1_points.all()
                            ma2_points = ma2_points.all()

                            if ma1_points and ma2_points:
                                # Convert points to the required format for intersection calculation
                                ma1_list = [{"date": point.date, "value": point.price} for point in ma1_points]
                                ma2_list = [{"date": point.date, "value": point.price} for point in ma2_points]

                                # Find intersections
                                intersection_points = await find_intersection(session, ma1_list, ma2_list)

                                existing_intersections = await session.scalars(select(MA_Lines_Intersection_Point).where(
                                    MA_Lines_Intersection_Point.symbol_id == symbol_id, 
                                    MA_Lines_Intersection_Point.line1_period == ma1_period, 
                                    MA_Lines_Intersection_Point.line2_period == ma2_period, 
                                    MA_Lines_Intersection_Point.bar_type == bar_type,
                                    MA_Lines_Intersection_Point.date >= start_date
                                ))
                                existing_intersections = existing_intersections.all()

                                if not existing_intersections and intersection_points:
                                    for point in intersection_points:
                                        new_intersection_point = MA_Lines_Intersection_Point(
                                            symbol_id=symbol_id, 
                                            line1_period=ma1_period, 
                                            line2_period=ma2_period, 
                                            bar_type=bar_type, 
                                            date=point[0], 
                                            price=point[1]
                                        )
                                        session.add(new_intersection_point)
                                    await session.commit()
                                elif existing_intersections and not intersection_points:
                                    await session.execute(delete(MA_Lines_Intersection_Point).where(
                                        MA_Lines_Intersection_Point.symbol_id == symbol_id, 
                                        MA_Lines_Intersection_Point.line1_period == ma1_period, 
                                        MA_Lines_Intersection_Point.line2_period == ma2_period, 
                                        MA_Lines_Intersection_Point.bar_type == bar_type,
                                        MA_Lines_Intersection_Point.date >= start_date
                                    ))
                                    await session.commit()
                                elif existing_intersections and intersection_points:
                                    await session.execute(delete(MA_Lines_Intersection_Point).where(
                                        MA_Lines_Intersection_Point.symbol_id == symbol_id, 
                                        MA_Lines_Intersection_Point.line1_period == ma1_period, 
                                        MA_Lines_Intersection_Point.line2_period == ma2_period, 
                                        MA_Lines_Intersection_Point.bar_type == bar_type,
                                        MA_Lines_Intersection_Point.date >= start_date
                                    ))
                                    for point in intersection_points:
                                        new_intersection_point = MA_Lines_Intersection_Point(
                                            symbol_id=symbol_id, 
                                            line1_period=ma1_period, 
                                            line2_period=ma2_period, 
                                            bar_type=bar_type, 
                                            date=point[0], 
                                            price=point[1]
                                        )
                                        session.add(new_intersection_point)
                                    await session.commit()
                                logger.info(f"Intersections for symbol {symbol_id} with periods {ma1_period} and {ma2_period} for bar type {bar_type}")
                except Exception as e:
                    logger.error(f"An error occurred while finding intersections: {e}")
                    raise e
                except sqlalchemy.exc.DBAPIError as e:
                    logger.error(f"Database error occurred: {e}")
                finally:
                    await session.close()
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Task failed.")
    return

async def generate_week_month_bars_from_tokyo_upload_task():
    async for session in get_session():
        try:
            symbol_ids = await session.scalars(select(Symbol.id).where(Symbol.category == "Stock"))
            symbol_ids = symbol_ids.all()
            
            for symbol_id in symbol_ids:
                new_day_bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1w").where(Bar.created_at >= datetime.now(tz=timezone.utc).replace(tzinfo=None)-timedelta(days=1)).order_by(Bar.from_time.asc()))
                new_day_bars = new_day_bars.all()

                if not new_day_bars:
                    continue

                for day_bar in new_day_bars:
                    monday = day_bar.from_time - timedelta(days=day_bar.from_time.weekday())
                    friday = day_bar.from_time + timedelta(days=4-day_bar.from_time.weekday())
                    existing_week_bar = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1w").where(Bar.from_time >= monday, Bar.to_time <= friday))
                    existing_week_bar = existing_week_bar.first()

                    if existing_week_bar is not None:
                        if day_bar.from_time < existing_week_bar.from_time:
                            new_open_price = day_bar.open
                        else:
                            new_day_bars = existing_week_bar.open
                            
                        if day_bar.to_time > existing_week_bar.to_time:
                            new_close_price = day_bar.close
                        else:
                            new_close_price = existing_week_bar.close

                        result = await session.execute(update(Bar).where(Bar.id == existing_week_bar.id).values(
                            from_time = min(existing_week_bar.from_time, day_bar.from_time),
                            to_time = max(existing_week_bar.to_time, day_bar.to_time),
                            high = max(existing_week_bar.high, day_bar.high),
                            low = min(existing_week_bar.low, day_bar.low),
                            open = new_open_price,
                            close = new_close_price 
                        ))
                        await session.commit()
                    else:
                        new_week_bar = Bar(
                            from_time = day_bar.from_time,
                            to_time = day_bar.to_time,
                            open = day_bar.open,
                            close = day_bar.close,
                            high = day_bar.high,
                            low = day_bar.low,
                            volume = day_bar.volume,
                            type = "1w",
                            symbol_id = day_bar.symbol_id
                        )

                        session.add(new_week_bar)
                        await session.commit()
                        

                    first_day_current_month = datetime(day_bar.from_time.year, day_bar.from_time.month, 1)
                    first_day_next_month = first_day_current_month + relativedelta(months=1)
                    existing_month_bar = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1m").where(Bar.from_time >= first_day_current_month, Bar.to_time<first_day_next_month))
                    existing_month_bar = existing_month_bar.first()
                        
                    if existing_month_bar is not None:
                        if day_bar.from_time < existing_month_bar.from_time:
                            new_open_price = day_bar.open
                        else:
                            new_day_bars = existing_month_bar.open
                            
                        if day_bar.to_time > existing_month_bar.to_time:
                            new_close_price = day_bar.close
                        else:
                            new_close_price = existing_month_bar.close
                        
                        result = await session.execute(update(Bar).where(Bar.id == existing_month_bar.id).values(
                            from_time = min(existing_month_bar.from_time, day_bar.from_time),
                            to_time = max(existing_month_bar.to_time, day_bar.to_time),
                            high = max(existing_month_bar.high, day_bar.high),
                            low = min(existing_month_bar.low, day_bar.low),
                            open = new_open_price,
                            close = new_close_price
                        ))
                        await session.commit()
                    else:
                        new_month_bar = Bar(
                            from_time = day_bar.from_time,
                            to_time = day_bar.to_time,
                            open = day_bar.open,
                            close = day_bar.close,
                            high = day_bar.high,
                            low = day_bar.low,
                            volume =day_bar.volume,
                            type = "1m",
                            symbol_id =day_bar.symbol_id
                        )

                        session.add(new_month_bar)
                        await session.commit()

        except Exception as e:
            logger.error(f"error {e}")
        finally:
            await session.close()

async def get_stock_symbol_ids():
    async for session in get_session():
        try:
            symbol_ids = await session.scalars(select(Symbol.id).where(Symbol.category == "Stock").order_by(Symbol.id))
            return symbol_ids.all()
        except Exception as e:
            logger.error(f"An error occurred while fetching stock symbol IDs: {e}")
            return []
        finally:
            await session.close()


async def calculate_provisional_bars_for_tokyo_upload_task(symbol_id: int):
    async for session in get_session():
        try:
            logger.info(f"Calculating provisional bars for symbol_id: {symbol_id}")
            # for bar_type in BAR_TYPES:
            bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1d").order_by(Bar.from_time.asc()))
            bars = bars.all()

            pre_bar = {}
            for index, bar in enumerate(bars):
                if index == 0:
                    pre_bar = {
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close
                    }
                    continue

                if index == 1:
                    provisional_open = (pre_bar['open'] + pre_bar['high'] + pre_bar['low'] + pre_bar['close']) / 4
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                else:
                    provisional_open = (pre_bar["provisional_open"] + pre_bar["provisional_close"]) / 2
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                pre_bar["provisional_open"] = provisional_open
                pre_bar["provisional_close"] = provisional_close

                result = await session.execute(update(Bar).where(Bar.id == bar.id).values(
                    provisional_open = provisional_open,
                    provisional_close = provisional_close
                ))
                await session.commit()

            # Calculate provisional_open and provisional_close for week and month bars
            week_bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1w").order_by(Bar.from_time.asc()))
            week_bars = week_bars.all()

            pre_bar = {}
            for index, bar in enumerate(week_bars):
                if index == 0:
                    pre_bar = {
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close
                    }
                    continue

                if index == 1:
                    provisional_open = (pre_bar['open'] + pre_bar['high'] + pre_bar['low'] + pre_bar['close']) / 4
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                else:
                    provisional_open = (pre_bar["provisional_open"] + pre_bar["provisional_close"]) / 2
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                pre_bar["provisional_open"] = provisional_open
                pre_bar["provisional_close"] = provisional_close

                result = await session.execute(update(Bar).where(Bar.id == bar.id).values(
                    provisional_open = provisional_open,
                    provisional_close = provisional_close
                ))
                await session.commit()

            # Calculate provisional_open and provisional_close for month bars
            month_bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1m").order_by(Bar.from_time.asc()))
            month_bars = month_bars.all()

            pre_bar = {}
            for index, bar in enumerate(month_bars):
                if index == 0:
                    pre_bar = {
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close
                    }
                    continue

                if index == 1:
                    provisional_open = (pre_bar['open'] + pre_bar['high'] + pre_bar['low'] + pre_bar['close']) / 4
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                else:
                    provisional_open = (pre_bar["provisional_open"] + pre_bar["provisional_close"]) / 2
                    provisional_close = (bar.open + bar.high + bar.low + bar.close) / 4
                pre_bar["provisional_open"] = provisional_open
                pre_bar["provisional_close"] = provisional_close

                result = await session.execute(update(Bar).where(Bar.id == bar.id).values(
                    provisional_open = provisional_open,
                    provisional_close = provisional_close
                ))
                await session.commit()

        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            await session.close()

async def generate_week_month_bars_for_base_data(symbol_id: int):
    async for session in get_session():
        try:
            logger.info(f"Processing week and month symbol_id: {symbol_id}")
            day_bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1d").order_by(Bar.from_time.asc()))
            day_bars = day_bars.all()

            if not day_bars:
                logging.info(f"No bars data for symbol <id: {symbol_id}> from Tokyo Stock Exchange")
                continue

            week_bars = await get_week_bars(symbol_id, day_bars, session)
            month_bars = await get_month_bars(symbol_id, day_bars, session)

            session.add_all(week_bars)
            await session.commit()
            
            session.add_all(month_bars)
            await session.commit()
        except Exception as e:
            logger.error(f"Error processing base data: {e}")
        finally:
            await session.close()

async def get_week_bars(symbol_id:int, day_bars:list[Bar], session: AsyncSession) -> list[Bar]:
    bars = []

    if not day_bars:
        return bars
    
    group = []

    for index, element in enumerate(day_bars):
        group.append(element)

        end_of_week = False
        if index < len(day_bars) -1:
            end_of_week = element.from_time.weekday() > day_bars[index+1].from_time.weekday()

        if end_of_week or index == len(day_bars) - 1:

            curr_bar = combine_bars_from_days(group, "1w", symbol_id)
            if bars:
                prev_bar = bars[-1]
                if len(bars) == 1:
                    curr_bar.provisional_open = (prev_bar.open + prev_bar.high + prev_bar.low + prev_bar.close) / 4
                else:
                    curr_bar.provisional_open = (prev_bar.provisional_open + prev_bar.provisional_close) / 2

                curr_bar.provisional_close = (curr_bar.open + curr_bar.high + curr_bar.low + curr_bar.close) / 4
            
            if curr_bar is not None:
                existing_bar = await session.scalar(
                    select(Bar).where(
                        Bar.type == "1w",
                        Bar.symbol_id == symbol_id,
                        Bar.from_time == curr_bar.from_time
                    )
                )
                
                if existing_bar is None:
                    bars.append(curr_bar)
                elif index == len(day_bars) - 1:
                    existing_bar.open = curr_bar.open
                    existing_bar.high = curr_bar.high
                    existing_bar.low = curr_bar.low
                    existing_bar.close = curr_bar.close
                    existing_bar.provisional_open = curr_bar.provisional_open
                    existing_bar.provisional_close = curr_bar.provisional_close
                    existing_bar.to_time = curr_bar.to_time
                    await session.commit()
            
            group = []

    return bars

async def get_month_bars(symbol_id:int, day_bars:list[Bar], session: AsyncSession) -> list[Bar]:
    bars = []

    if not day_bars:
        return bars
    
    group = []

    for index, element in enumerate(day_bars):        
        group.append(element)
        
        end_of_month = False
        if index < len(day_bars) - 1:
            end_of_month = element.from_time.month != day_bars[index+1].from_time.month

        if end_of_month or index == len(day_bars) - 1:
            curr_bar = combine_bars_from_days(group, "1m", symbol_id)

            if bars:
                prev_bar = bars[-1]
                if len(bars) == 1:
                    curr_bar.provisional_open = (prev_bar.open + prev_bar.high + prev_bar.low + prev_bar.close) / 4
                else:
                    curr_bar.provisional_open = (prev_bar.provisional_open + prev_bar.provisional_close) / 2

                curr_bar.provisional_close = (curr_bar.open + curr_bar.high + curr_bar.low + curr_bar.close) / 4
            
            if curr_bar is not None:
                existing_bar = await session.scalar(
                    select(Bar).where(
                        Bar.type == "1m",
                        Bar.symbol_id == symbol_id,
                        Bar.from_time == curr_bar.from_time
                    )
                )
                
                if existing_bar is None:
                    bars.append(curr_bar)
                elif index == len(day_bars) - 1:
                    existing_bar.open = curr_bar.open
                    existing_bar.high = curr_bar.high
                    existing_bar.low = curr_bar.low
                    existing_bar.close = curr_bar.close
                    existing_bar.provisional_open = curr_bar.provisional_open
                    existing_bar.provisional_close = curr_bar.provisional_close
                    existing_bar.to_time = curr_bar.to_time
                    await session.commit()
            
            group = []
 
    return bars

def combine_bars_from_days(bars:list[Bar], type:str, symbol_id:int) -> Bar:
    if not bars:
        return None
    
    to_bar = bars[-1]
    from_bar = bars[0]

    bar = Bar(
        from_time = from_bar.from_time,
        to_time = to_bar.to_time,
        open = from_bar.open,
        close = to_bar.close,
        high = max([bar.high for bar in bars]),
        low = min([bar.low for bar in bars]),
        volume = sum([bar.volume for bar in bars]),
        type = type,
        symbol_id = symbol_id
    )

    return bar
