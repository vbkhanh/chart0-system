import asyncio
from app.models import Bar, Symbol
from app.configs.db import get_session
import logging
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def generate_week_month_bars_for_base_data():
    async for session in get_session():
        try:
            symbol_ids = await session.scalars(select(Symbol.id).where(Symbol.category == "Stock"))
            symbol_ids = symbol_ids.all()

            for symbol_id in symbol_ids:
                day_bars = await session.scalars(select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == "1d").order_by(Bar.from_time.asc()))
                day_bars = day_bars.all()

                if not day_bars:
                    logging.info(f"No bars data for symbol <id: {symbol_id}> from Tokyo Stock Exchange")
                    continue

                week_bars = get_week_bars(symbol_id, day_bars)
                month_bars = get_month_bars(symbol_id, day_bars)

                session.add_all(week_bars)
                await session.commit()
                
                session.add_all(month_bars)
                await session.commit()

        except Exception as e:
            logger.error(f"Error processing base data: {e}")
        finally:
            await session.close()

def get_week_bars(symbol_id:int, day_bars:list[Bar]) -> list[Bar]:
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
                bars.append(curr_bar)
            
            group = []

    return bars

def get_month_bars(symbol_id:int, day_bars:list[Bar]) -> list[Bar]:
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
                bars.append(curr_bar)
            
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


if __name__ == "__main__":
    asyncio.run(generate_week_month_bars_for_base_data())