from celery_task.celery_app import celery_app
from celery_task.cronlogic import (
    calculate_MA_task, find_intersection_task,
    generate_week_month_bars_from_tokyo_upload_task,
    calculate_provisional_bars_for_tokyo_upload_task,
    generate_week_month_bars_for_base_data,
    get_stock_symbol_ids,
    get_all_symbol_ids
)
import asyncio
import datetime

logger = celery_app.log.get_default_logger()

@celery_app.task(name="calculate_MA_task")
def cronjob_calculate_MA_task(start_date: str = None, end_date: str = None, calculate_intersection: bool = True):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    symbol_ids = loop.run_until_complete(get_all_symbol_ids())
    for symbol_id in symbol_ids:
        processing_MA_task.apply_async(args=[symbol_id, start_date, end_date])
    if calculate_intersection:
        for symbol_id in symbol_ids:
            cronjob_find_intersection_task.apply_async(args=[symbol_id, start_date, end_date])

@celery_app.task(name="processing_MA_task")
def processing_MA_task(symbol_id: int, start_date: str = None, end_date: str = None):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    if start_date is not None:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date is not None:
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    loop.run_until_complete(calculate_MA_task(symbol_id, start_date, end_date))

@celery_app.task(name="find_intersection_task")
def cronjob_find_intersection_task(symbol_id: int, start_date: str = None, end_date: str = None):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    if start_date is not None:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date is not None:
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    loop.run_until_complete(find_intersection_task(symbol_id, start_date, end_date))

@celery_app.task(name="generate_week_month_bars_from_tokyo_upload_task")
def cronjob_generate_week_month_bars_from_tokyo_upload_task():
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(generate_week_month_bars_from_tokyo_upload_task())

@celery_app.task(name="generate_week_month_bars_from_tokyo_upload_task_for_all")
def cronjob_generate_week_month_bars_from_tokyo_upload_task_for_all():
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    symbol_ids = loop.run_until_complete(get_stock_symbol_ids())
    for symbol_id in symbol_ids:
        cronjob_generate_week_month_bars_from_tokyo_upload_task_by_symbol_id.apply_async(args=[symbol_id])

@celery_app.task(name="generate_week_month_bars_from_tokyo_upload_task_by_symbol_id")
def cronjob_generate_week_month_bars_from_tokyo_upload_task_by_symbol_id(symbol_id: int):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(generate_week_month_bars_for_base_data(symbol_id))    

@celery_app.task(name="get_stock_symbol_ids")
def cronjob_get_stock_symbol_ids():
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    symbol_ids = loop.run_until_complete(get_stock_symbol_ids())
    for symbol_id in symbol_ids:
        cronjob_calculate_provisional_bars_for_tokyo_upload_task.apply_async(args=[symbol_id])
    
@celery_app.task(name="calculate_provisional_bars_for_tokyo_upload_task")
def cronjob_calculate_provisional_bars_for_tokyo_upload_task(symbol_id: int):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(calculate_provisional_bars_for_tokyo_upload_task(symbol_id))