import pandas as pd
import asyncio
from app.models import Symbol
from app.configs.db import get_session
import logging
import json
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def insert_symbol_from_excel(file_path: str):
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        with open('scripts/stock-name-translation.json', 'r', encoding='utf-8') as file:
            japanese_name = json.load(file)
        # Parse to dict like [{"column_name": value}]
        data = [{col: row[col] for col in df.columns} for _, row in df.iterrows()]

        async for session in get_session():
            try:
                # Iterate over DataFrame rows
                for symbol_info in data:
                    try:
                        # print(f"Processing symbol {symbol_info['Name (English)']}")
                        # Check if a Symbol with the same code already exists
                        existing_symbol = await session.execute(
                            select(Symbol).where(Symbol.code == f"{symbol_info['Local Code']}0")
                        )
                        existing_symbol = existing_symbol.scalar_one_or_none()

                        if existing_symbol:
                            # print(f"Updating existing symbol: {existing_symbol.name}")
                            # Update the existing Symbol
                            existing_symbol.japanese_name = japanese_name[existing_symbol.name]
                            existing_symbol.symbol_info = symbol_info
                            await session.commit()
                        else:
                            # Create a new Symbol object
                            new_symbol = Symbol(
                                name=symbol_info['Name (English)'],
                                description=symbol_info['Name (English)'],
                                code=f"{symbol_info['Local Code']}0",
                                category="Stock",
                                symbol_info=symbol_info
                            )
                            # Add the new Symbol to the session
                            session.add(new_symbol)
                            await session.commit()

                    except Exception as e:
                        await session.rollback()
                        print(f"Error: Processing symbol {symbol_info['Name (English)']}")
                        print(e)
                
                return True

            except Exception as e:
                logger.error(f"Error processing DataFrame: {e}")
                return False
            finally:
                await session.close()

    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        return False

# Example usage
asyncio.run(insert_symbol_from_excel('scripts/company_name.xlsx'))
