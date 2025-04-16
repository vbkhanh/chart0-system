import pandas as pd
import os, time
import asyncio
from app.models import Symbol, Bar
from app.configs.db import get_session
import logging
from sqlalchemy import select
from datetime import datetime

logger = logging.getLogger(__name__)

async def insert_bar_from_csv(file_path: str):
    try:
        # Read the CSV file
        df = pd.read_csv(file_path, encoding='shift_jis')
        # Parse to dict like [{"column_name": value}]
        data = [
            {col: row[col] for col in df.columns}
            for _, row in df.iterrows()
            if not any(pd.isna(row[col]) for col in ['日通し始値', '日通し高値', '日通し安値', '日通し終値'])
        ]

        async for session in get_session():
            try:
                new_bars = []  # List to hold new Bar objects

                # Iterate over DataFrame rows
                for row in data:
                    try:
                        # Convert date from string to date object
                        date_str = row['日付']
                        row['日付'] = datetime.strptime(str(date_str), '%Y%m%d').date()

                        # Check if a Symbol with the same code already exists
                        existing_symbol = await session.execute(
                            select(Symbol).where(Symbol.code == str(row['銘柄コード']))
                        )
                        existing_symbol = existing_symbol.scalar_one_or_none()

                        if existing_symbol:
                            # Check if a Bar with the same date and symbol_id already exists
                            existing_bar = await session.execute(
                                select(Bar).where(
                                    Bar.from_time == row['日付'],
                                    Bar.symbol_id == existing_symbol.id,
                                    Bar.type == '1d'
                                )
                            )
                            existing_bar = existing_bar.scalar_one_or_none()

                            if existing_bar:
                                # Update the existing Bar
                                existing_bar.open = row['日通し始値']
                                existing_bar.high = row['日通し高値']
                                existing_bar.low = row['日通し安値']
                                existing_bar.close = row['日通し終値']
                                existing_bar.volume = row['売買高']
                            else:
                                # Create a new Bar object and add to the list
                                new_bar = Bar(
                                    from_time=row['日付'],
                                    to_time=row['日付'],
                                    open=row['日通し始値'],
                                    high=row['日通し高値'],
                                    low=row['日通し安値'],
                                    close=row['日通し終値'],
                                    provisional_open=None,
                                    provisional_close=None,
                                    volume=row['売買高'],
                                    type="1d",
                                    symbol_id=existing_symbol.id
                                )
                                new_bars.append(new_bar)

                    except Exception as e:
                        await session.rollback()
                        print(f"Error: Processing bar for date {row['日付']}")
                        print(e)

                # Add all new bars to the session at once
                if new_bars:
                    session.add_all(new_bars)

                await session.commit()
                return True

            except Exception as e:
                logger.error(f"Error processing DataFrame: {e}")
                return False
            finally:
                await session.close()

    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return False


async def process_file(folder):
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                print(f"Processing {file}")
                file_start_time = time.time()  # Start timing for processing a file
                await insert_bar_from_csv(file_path)
                file_end_time = time.time()  # End timing for processing a file
                print(f"Time taken to process file {file}: {file_end_time - file_start_time:.4f} seconds")


# Define the directory containing the old files
new_folder_path = 'scripts/new_2019_2021'

# Iterate over all files in the old folder
asyncio.run(process_file(new_folder_path))
