import pandas as pd
import os, time
import asyncio
from app.models import Symbol, Bar
from app.configs.db import get_session
import logging
from sqlalchemy import select
from datetime import datetime

logger = logging.getLogger(__name__)
symbol_exist_dict = {}

# async def insert_bar_from_csv(file_path: str):
#     global symbol_exist_dict
#     try:
#         # Read the CSV file
#         df = pd.read_csv(file_path)

#         # Parse to dict like [{"column_name": value}]
#         data = [
#             {col: row[col] for col in df.columns}
#             for _, row in df.iterrows()
#             if not any(pd.isna(row[col]) for col in ['Open', 'High', 'Low', 'Close'])
#         ]

#         async for session in get_session():
#             try:
#                 new_bars = []  # List to hold new Bar objects
#                 # Iterate over DataFrame rows
#                 for row in data:
#                     try:
#                         # Convert date from string to date object
#                         date_str = row['Date']
#                         row['Date'] = datetime.strptime(str(date_str), '%Y%m%d').date()

#                         if row['Issue code'] not in symbol_exist_dict:
#                             # Check if a Symbol with the same code already exists
#                             existing_symbol = await session.execute(
#                                 select(Symbol).where(Symbol.code == str(row['Issue code']))
#                             )
#                             existing_symbol = existing_symbol.scalar_one_or_none()
#                             symbol_exist_dict[row['Issue code']] = existing_symbol
#                         else:
#                             existing_symbol = symbol_exist_dict[row['Issue code']]

#                         if existing_symbol:
#                             # Check if a Bar with the same date and symbol_id already exists
#                             existing_bar = await session.execute(
#                                 select(Bar).where(
#                                     Bar.from_time == row['Date'],
#                                     Bar.symbol_id == existing_symbol.id,
#                                     Bar.type == '1d'
#                                 )
#                             )
#                             existing_bar = existing_bar.scalar_one_or_none()

#                             if existing_bar:
#                                 # Update the existing Bar
#                                 existing_bar.open = row['Open']
#                                 existing_bar.high = row['High']
#                                 existing_bar.low = row['Low']
#                                 existing_bar.close = row['Close']
#                                 existing_bar.volume = row['Trading volume']
#                             else:
#                                 # Create a new Bar object and add to the list
#                                 new_bar = Bar(
#                                     from_time=row['Date'],
#                                     to_time=row['Date'],
#                                     open=row['Open'],
#                                     high=row['High'],
#                                     low=row['Low'],
#                                     close=row['Close'],
#                                     provisional_open=None,
#                                     provisional_close=None,
#                                     volume=row['Trading volume'],
#                                     type="1d",
#                                     symbol_id=existing_symbol.id
#                                 )
#                                 new_bars.append(new_bar)

#                     except Exception as e:
#                         await session.rollback()
#                         print(f"Error: Processing bar for date {row['Date']}")
#                         print(e)

#                 # Add all new bars to the session at once
#                 if new_bars:
#                     session.add_all(new_bars)

#                 await session.commit()
#                 return True

#             except Exception as e:
#                 logger.error(f"Error processing DataFrame: {e}")
#                 return False
#             finally:
#                 await session.close()

#     except Exception as e:
#         logger.error(f"Error reading CSV file: {e}")
#         return False

async def insert_bar_from_csv(file_path: str):
    global symbol_exist_dict
    try:
        # Read the CSV file in chunks
        for chunk in pd.read_csv(file_path, chunksize=10000):
            chunk.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
            data = chunk.to_dict(orient='records')
            async for session in get_session():
                try:
                    for row in data:
                        date_str = row['Date']
                        row['Date'] = datetime.strptime(str(date_str), '%Y%m%d').date()
                        
                    # Fetch new symbols
                    new_symbols = [str(row['Issue code']) for row in data if str(row['Issue code']) not in symbol_exist_dict]
                    symbols = await session.execute(
                        select(Symbol).where(Symbol.code.in_(new_symbols))
                    )
                    symbols = symbols.scalars().all()
                    
                    for symbol in symbols:
                        if symbol.code is not None:
                            symbol_exist_dict[symbol.code] = symbol.id
                    
                    # Fetch existing bars
                    symbol_ids = [symbol_exist_dict.get(str(row['Issue code']), None) for row in data]
                    symbol_ids = [symbol_id for symbol_id in symbol_ids if symbol_id]
                    existing_bars = await session.execute(
                        select(Bar).where(
                            Bar.type == '1d',
                            Bar.from_time.in_([row['Date'] for row in data]),
                            Bar.symbol_id.in_(symbol_ids)
                        )
                    )
                    existing_bars = existing_bars.scalars().all()
                    existing_bars_dict = {(bar.from_time, bar.symbol_id): bar for bar in existing_bars}
                    
                    new_bars = []
                    for row in data:
                        existing_symbol_id = symbol_exist_dict.get(str(row['Issue code']))
                        if existing_symbol_id:
                            existing_bar = existing_bars_dict.get((row['Date'], existing_symbol_id))
                            
                            if existing_bar:
                                existing_bar.open = row['Open']
                                existing_bar.high = row['High']
                                existing_bar.low = row['Low']
                                existing_bar.close = row['Close']
                                existing_bar.volume = row['Trading volume']
                            else:
                                new_bar = Bar(
                                    from_time=row['Date'],
                                    to_time=row['Date'],
                                    open=row['Open'],
                                    high=row['High'],
                                    low=row['Low'],
                                    close=row['Close'],
                                    provisional_open=None,
                                    provisional_close=None,
                                    volume=row['Trading volume'],
                                    type="1d",
                                    symbol_id=existing_symbol_id
                                )
                                new_bars.append(new_bar)
                    
                    if new_bars:
                        session.add_all(new_bars)
                    
                    await session.commit()
                    print(f"Added {len(new_bars)} bars")
                
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error processing DataFrame: {e}")
                    return False
                finally:
                    await session.close()
    
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return False


async def process_file(folder):
    for root, dirs, files in os.walk(old_folder_path):
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                print(f"Processing {file}")
                file_start_time = time.time()  # Start timing for processing a file
                await insert_bar_from_csv(file_path)
                file_end_time = time.time()  # End timing for processing a file
                print(f"Time taken to process file {file}: {file_end_time - file_start_time:.4f} seconds")


# Define the directory containing the old files
old_folder_path = 'scripts/old'

# Iterate over all files in the old folder
asyncio.run(process_file(old_folder_path))
