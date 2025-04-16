from celery_task.celery_app import celery_app
from celery_task.cronjob import processing_MA_task, cronjob_find_intersection_task
from app.settings import settings
from azure.storage.blob import BlobServiceClient
from app.configs.db import get_session
from app.models import TokyoStock, Bar, Symbol, ExportFile, MA_Line_Point
from app.constants import TOKYO_STOCK_BLOB_CONTAINER, TOKYO_STOCK_MAPPING
from sqlalchemy import update, select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from typing import List, Dict
from datetime import datetime, timedelta, date
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from io import BytesIO
import asyncio

pd.options.display.unicode.east_asian_width = True
logger = celery_app.log.get_default_logger()

def handle_retry(
    self,
    e,
    count_down=300,
    retries_time=settings.CELERY_RETRIES_TIME,
):
    try:
        self.retry(exc=e, countdown=count_down)
    except Exception as e:
        raise e

@celery_app.task(
    bind=True,
    name="process_tokyo_stock_file",
    max_retries=settings.CELERY_RETRIES_TIME,
)
def process_tokyo_stock_file(self, file_name: str, file_format: str, tokyo_stock_id: int):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info(f"Received file: {file_name}")
        # Connect to Azure Blob Storage
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(TOKYO_STOCK_BLOB_CONTAINER)
        blob_client = container_client.get_blob_client(file_name)

        # Download the file content
        try:
            file_content = blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"File not found: {file_name}. Error: {e}")
            return f"Error: File {file_name} not found."

        if file_format == 'csv':
            df = pd.read_csv(BytesIO(file_content), encoding="shift_jis")
        elif file_format == 'excel':
            df = pd.read_excel(BytesIO(file_content))
        
        data = [{col: row[col] for col in df.columns} for _, row in df.iterrows()]

        res = loop.run_until_complete(store_to_bar_table(data, tokyo_stock_id))
        symbol_ids, time = res
        loop.run_until_complete(update_tokyo_stock_status(tokyo_stock_id, "Completed" if res is not False else "Failed"))
        for symbol_id in symbol_ids:
            generate_week_month_bars_task.apply_async(args=[tokyo_stock_id, symbol_id, time])

        for symbol_id in symbol_ids:
            from_time = datetime.strptime(str(time), '%Y%m%d').strftime('%Y-%m-%d')
            processing_MA_task.apply_async(args=[symbol_id, from_time, from_time])


    except Exception as e:
        handle_retry(self, e)

    return "File processed and stored successfully"

@celery_app.task(
    bind=True,
    name="generate_week_month_bars_task",
    max_retries=settings.CELERY_RETRIES_TIME,
)
def generate_week_month_bars_task(self, tokyo_stock_id: int, symbol_id: int, to_time: str):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info(f"Starting generation of week and month bars for symbol_id: {symbol_id} up to {to_time}")
        to_time = datetime.strptime(str(to_time), '%Y%m%d').date()
        loop.run_until_complete(generate_week_month_bars(tokyo_stock_id, symbol_id, to_time))

    except Exception as e:
        handle_retry(self, e)

    return "Week and month bars generated successfully"


@celery_app.task(
    bind=True,
    name="cleanup_tokyo_stock_data",
    max_retries=settings.CELERY_RETRIES_TIME,
)
def cleanup_tokyo_stock_data(self, tokyo_stock_id: int, file_name: str):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info(f"Cleaning up data for Tokyo Stock ID: {tokyo_stock_id}")
        
        # Delete Bar records with the given tokyo_stock_id
        loop.run_until_complete(delete_bar_records(tokyo_stock_id))

        # Connect to Azure Blob Storage
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(TOKYO_STOCK_BLOB_CONTAINER)
        blob_client = container_client.get_blob_client(file_name)

        # Delete the file from Azure Blob Storage
        try:
            blob_client.delete_blob()
            logger.info(f"File {file_name} deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete file: {file_name}. Error: {e}")
        
        loop.run_until_complete(delete_tokyo_stock_record(tokyo_stock_id))

    except Exception as e:
        handle_retry(self, e)

    return "Cleanup completed successfully"

@celery_app.task(
    bind=True,
    name="export_bar_data",
    max_retries=settings.CELERY_RETRIES_TIME,
)
def export_bar_data(self, payload: Dict):
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info(f"Starting export for file: {payload['file_name']} from {payload['start_date']} to {payload['end_date']}")

        # Get bar data from database
        bars = loop.run_until_complete(get_bar_data(
            payload['symbol_id'],
            payload['start_date'],
            payload['end_date']
        ))

        if not bars:
            loop.run_until_complete(update_export_file_status(payload['file_name'], "Failed"))
            return "No data found for export"

        # Convert to DataFrame
        bar_list = []
        for bar in bars:
            if payload['language'] == 'en':
                if bar.provisional_open is not None:
                    up_down = 'Up' if bar.provisional_close > bar.provisional_open  else 'Down'
                else:
                    up_down = 'Down'
                bar_list.append({
                    'Date': bar.from_time,
                    'Open': bar.open,
                    'Close': bar.close,
                    'High': bar.high,
                    'Low': bar.low,
                    'Up/Down': up_down
                })
            else:  # 'jp'
                if bar.provisional_open is not None:
                    up_down = '陽' if bar.provisional_close > bar.provisional_open  else '陰'
                else:
                    up_down = '陰'
                bar_list.append({
                    '日付': bar.from_time,
                    '始値': bar.open,
                    '終値': bar.close,
                    '高値': bar.high,
                    '安値': bar.low,
                    '陽/陰': up_down
                })
        df = pd.DataFrame(bar_list)

        # Create file in memory
        output = BytesIO()
        if payload['format'].lower() == 'csv':
            df.to_csv(output, index=False)
            content_type = 'text/csv'
        else:  # Excel
            df.to_excel(output, index=False)
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        output.seek(0)

        if payload['format'].lower() != 'csv':
            wb = load_workbook(output)
            ws = wb.active

            # Adjust column width
            ws.column_dimensions['A'].width = 30  # Set column A width

            # Center align column F
            for cell in ws['F']:
                cell.alignment = Alignment(horizontal="center")

            # Save back to BytesIO
            output = BytesIO()
            wb.save(output)
            output.seek(0)

        # Upload to blob storage
        blob_service_client = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(TOKYO_STOCK_BLOB_CONTAINER)
        blob_client = container_client.get_blob_client(payload['file_name'])

        blob_client.upload_blob(output.getvalue(), content_type=content_type, overwrite=True)
        
        file_size = len(output.getvalue())
        loop.run_until_complete(update_export_file_status(payload['file_name'], "Completed", file_size))

    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        loop.run_until_complete(update_export_file_status(payload['file_name'], "Failed"))
        handle_retry(self, e)
    finally:
        output.close()
    return "Export completed successfully"

async def delete_bar_records(tokyo_stock_id: int):
    async for session in get_session():
        try:
            result = await session.execute(
                select(Bar.id, Bar.symbol_id, Bar.from_time).where(Bar.tokyo_stock_id == tokyo_stock_id)
            )
            bars = result.all()

            if bars:
                for bar in bars:
                    await session.execute(
                        delete(MA_Line_Point).where(
                            MA_Line_Point.symbol_id == bar.symbol_id,
                            MA_Line_Point.date == bar.from_time
                        )
                    )
                bar_ids = [bar.id for bar in bars]
                await session.execute(
                    delete(Bar).where(Bar.id.in_(bar_ids))
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to delete Bar records for Tokyo Stock ID: {tokyo_stock_id}. Error: {e}")
            raise e

async def delete_tokyo_stock_record(tokyo_stock_id: int):
    async for session in get_session():
        try:
            # Delete the TokyoStock record with the given id
            await session.execute(
                delete(TokyoStock).where(TokyoStock.id == tokyo_stock_id)
            )
            await session.commit()
            logger.info(f"TokyoStock record with ID {tokyo_stock_id} deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete TokyoStock record with ID {tokyo_stock_id}. Error: {e}")
            raise e
        finally:
            await session.close()

async def get_bar_data(symbol_id: int, start_date: datetime, end_date: datetime):
    async for session in get_session():
        try:
            result = await session.execute(
                select(Bar).where(
                    Bar.symbol_id == symbol_id,
                    Bar.from_time >= start_date,
                    Bar.from_time <= end_date,
                    Bar.type == '1d'
                ).order_by(Bar.from_time.desc())
            )
            return result.scalars().all()
        finally:
            await session.close()

async def update_export_file_status(file_name: str, status: str, file_size: int = None):
    async for session in get_session():
        try:
            update_values = {}
            if status is not None:
                update_values['processing_status'] = status
            if file_size is not None:
                update_values['file_size'] = file_size
                
            if update_values:
                await session.execute(
                    update(ExportFile)
                    .where(ExportFile.file_name == file_name)
                    .values(**update_values)
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Error updating ExportFile status for {file_name}: {e}")
        finally:
            await session.close()

async def store_to_bar_table(data: List[Dict], tokyo_stock_id: int):
    async for session in get_session():
        try:
            date_time = datetime.strptime(str(data[0][TOKYO_STOCK_MAPPING['date']]), '%Y%m%d').date()
            prev_data = await session.execute(
                select(Symbol.id, Bar.from_time.label('prev_date'), Bar.open, Bar.close, Bar.high, Bar.low, Bar.provisional_open, Bar.provisional_close)
                .join(Bar, Symbol.id == Bar.symbol_id)
                .where(
                    Symbol.category == 'Stock',
                    Bar.from_time == select(func.max(Bar.from_time))
                    .where(
                        Bar.symbol_id == Symbol.id,
                        Bar.from_time < date_time
                    ).correlate(Symbol)
                )
            )
            prev_data = {row.id: row for row in prev_data.all()}
            symbol_ids = []
            for row in data:
                try:
                    date_str = row[TOKYO_STOCK_MAPPING['date']]
                    row[TOKYO_STOCK_MAPPING['date']] = datetime.strptime(str(date_str), '%Y%m%d').date()
                    if isinstance(row[TOKYO_STOCK_MAPPING['security code']], str):
                        row[TOKYO_STOCK_MAPPING['security code']] = row[TOKYO_STOCK_MAPPING['security code']].replace(" ", "")
                    # Check if a Bar with the same date and symbol_id already exists
                    existing_symbol = await session.execute(
                        select(Symbol).where(Symbol.code == str(row[TOKYO_STOCK_MAPPING['security code']]))
                    )
                    existing_symbol = existing_symbol.scalar_one_or_none()
                    if existing_symbol:
                        symbol_ids.append(existing_symbol.id)
                        existing_bar = await session.execute(
                            select(Bar).where(
                                Bar.from_time == row[TOKYO_STOCK_MAPPING['date']],
                                Bar.symbol_id == existing_symbol.id,
                                Bar.type == '1d'
                            )
                        )
                        existing_bar = existing_bar.scalar_one_or_none()

                        prev_record = prev_data.get(existing_symbol.id)
                        if prev_record:
                            if prev_record.provisional_open is not None:
                                provisional_open = (prev_record.provisional_open + prev_record.provisional_close) / 2
                            else:
                                provisional_open = (prev_record.open + prev_record.high + prev_record.low + prev_record.close) / 4
                        else:
                            provisional_open = None
                        provisional_close = (row[TOKYO_STOCK_MAPPING['all-day opening price']] +
                                            row[TOKYO_STOCK_MAPPING['all-day high price']] +
                                            row[TOKYO_STOCK_MAPPING['all-day low price']] +
                                            row[TOKYO_STOCK_MAPPING['all-day closing price']]) / 4

                        if existing_bar:
                            # Update the existing Bar
                            existing_bar.open = row[TOKYO_STOCK_MAPPING['all-day opening price']]
                            existing_bar.high = row[TOKYO_STOCK_MAPPING['all-day high price']]
                            existing_bar.low = row[TOKYO_STOCK_MAPPING['all-day low price']]
                            existing_bar.close = row[TOKYO_STOCK_MAPPING['all-day closing price']]
                            existing_bar.volume = row[TOKYO_STOCK_MAPPING['trading volume']]
                            existing_bar.tokyo_stock_id = tokyo_stock_id
                            existing_bar.provisional_open = provisional_open
                            existing_bar.provisional_close = provisional_close
                        else:
                            # Create a new Bar object
                            new_bar = Bar(
                                from_time=row[TOKYO_STOCK_MAPPING['date']],
                                to_time=row[TOKYO_STOCK_MAPPING['date']],
                                open=row[TOKYO_STOCK_MAPPING['all-day opening price']],
                                high=row[TOKYO_STOCK_MAPPING['all-day high price']],
                                low=row[TOKYO_STOCK_MAPPING['all-day low price']],
                                close=row[TOKYO_STOCK_MAPPING['all-day closing price']],
                                provisional_open=provisional_open,
                                provisional_close=provisional_close,
                                volume=row[TOKYO_STOCK_MAPPING['trading volume']],
                                type="1d",
                                symbol_id=existing_symbol.id,
                                tokyo_stock_id=tokyo_stock_id
                            )
                            # Add the new Bar to the session
                            session.add(new_bar)

                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    return False

            # Commit the session to store all bars
            await session.commit()
            return (symbol_ids, date_str)

        except Exception as e:
            logger.error(f"Error processing DataFrame: {e}")
            return False
        finally:
            await session.close()

async def update_tokyo_stock_status(tokyo_stock_id: int, status: str):
    async for session in get_session():
        try:
            # Update the processing_status of the TokyoStock entry with the given file_name
            await session.execute(
                update(TokyoStock)
                .where(TokyoStock.id == tokyo_stock_id)
                .values(processing_status=status)
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Error updating TokyoStock status for {tokyo_stock_id}: {e}")
        finally:
            await session.close()

async def generate_week_month_bars(tokyo_stock_id: int, symbol_id: int, to_time: date):
    async for session in get_session():
        try:
            logger.info(f"Processing week and month symbol_id: {symbol_id}")
            ## Process week ##
            await session.execute(
                delete(Bar).where(
                    Bar.type == "1w",
                    Bar.symbol_id == symbol_id,
                    Bar.from_time >= to_time - timedelta(days=to_time.weekday()),
                    Bar.from_time <= to_time
                )
            )
            last_week_bar = await session.scalar(
                select(Bar)
                .where(Bar.type == "1w", Bar.symbol_id == symbol_id)
                .order_by(Bar.from_time.desc())
                .limit(1)
            )
            # Fetch data within the week
            day_bars = await session.scalars(
                select(Bar).where(
                    Bar.type == "1d",
                    Bar.symbol_id == symbol_id,
                    Bar.from_time >= to_time - timedelta(days=to_time.weekday()),
                    Bar.from_time <= to_time
                ).order_by(Bar.from_time.asc())
            )
            day_bars = day_bars.all()

            new_week_bar = combine_bars_from_days(day_bars, "1w", symbol_id)
            if last_week_bar:
                if last_week_bar.provisional_open:
                    new_week_bar.provisional_open = (last_week_bar.provisional_open + last_week_bar.provisional_close) / 2
                else:
                    new_week_bar.provisional_open = (last_week_bar.open + last_week_bar.high + last_week_bar.low + last_week_bar.close) / 4
            new_week_bar.provisional_close = (new_week_bar.open + new_week_bar.high + new_week_bar.low + new_week_bar.close) / 4
            new_week_bar.tokyo_stock_id = tokyo_stock_id
            session.add(new_week_bar)

            ## Processing month
            await session.execute(
                delete(Bar).where(
                    Bar.type == "1m",
                    Bar.symbol_id == symbol_id,
                    Bar.from_time >= to_time.replace(day=1),
                    Bar.from_time <= to_time.replace(month=to_time.month % 12 + 1, day=1) - timedelta(days=1)
                )
            )
            last_month_bar = await session.scalar(
                select(Bar)
                .where(Bar.type == "1m", Bar.symbol_id == symbol_id)
                .order_by(Bar.from_time.desc())
                .limit(1)
            )
            # Fetch data within the month
            day_bars = await session.scalars(
                select(Bar).where(
                    Bar.type == "1d",
                    Bar.symbol_id == symbol_id,
                    Bar.from_time >= to_time.replace(day=1),
                    Bar.from_time <= to_time.replace(month=to_time.month % 12 + 1, day=1) - timedelta(days=1)
                ).order_by(Bar.from_time.asc())
            )
            day_bars = day_bars.all()

            new_month_bar = combine_bars_from_days(day_bars, "1m", symbol_id)
            if last_month_bar:
                if last_month_bar.provisional_open:
                    new_month_bar.provisional_open = (last_month_bar.provisional_open + last_month_bar.provisional_close) / 2
                else:
                    new_month_bar.provisional_open = (last_month_bar.open + last_month_bar.high + last_month_bar.low + last_month_bar.close) / 4
            new_month_bar.provisional_close = (new_month_bar.open + new_month_bar.high + new_month_bar.low + new_month_bar.close) / 4
            new_month_bar.tokyo_stock_id = tokyo_stock_id
            session.add(new_month_bar)

            # Commit the session to save changes
            await session.commit()
        except Exception as e:
            logger.error(f"Error processing base data: {e}")
        finally:
            await session.close()

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
