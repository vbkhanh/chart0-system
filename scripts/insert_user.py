import pandas as pd
import asyncio
from app.models import User
from app.configs.db import get_session
from app.utils import hash_password
import logging
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def insert_users_from_csv(file_path: str):
    try:
        # Read the CSV file
        print(file_path)
        df = pd.read_csv(file_path)
        # Parse to dict like [{"column_name": value}]
        data = [
            {col: row[col] for col in df.columns}
            for _, row in df.iterrows()
            if not pd.isna(row['Email address'])
        ]

        async for session in get_session():
            try:
                new_users = []  # List to hold new User objects

                # Iterate over DataFrame rows
                for row in data:
                    print(f"Processing user with email: {row['Email address']}")
                    try:
                        # Check if a User with the same email already exists
                        existing_user = await session.execute(
                            select(User).where(User.email == row['Email address'])
                        )
                        existing_user = existing_user.scalar_one_or_none()

                        if not existing_user:
                            
                            email_prefix = row['Email address'].split('@')[0]
                            encrypted_password = hash_password(email_prefix)
                            user_data = {
                                "email": row['Email address'],
                                "full_name": row['Name in Kanji'],
                                "hiragana_name": row['Name in Hiragana'],
                                "encrypted_password": encrypted_password,
                                "status": "approved",
                                "state": "enabled",
                                "is_verified": True
                            }
                            if not pd.isna(row['Registered Date']):
                                user_data["created_at"] = pd.to_datetime(row['Registered Date'], format='%m/%d/%Y %H:%M')
                            new_user = User(
                                **user_data
                            )
                            new_users.append(new_user)
                        else:
                            # Update the existing user's information
                            existing_user.status = "approved"
                            existing_user.state = "enabled"
                            existing_user.is_verified = True

                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Error: Processing user with email {row['Email address']}")
                        logger.error(e)

                # Add all new users to the session at once
                if new_users:
                    session.add_all(new_users)

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

async def main():
    file_path = 'scripts/user_data.csv'
    await insert_users_from_csv(file_path)

if __name__ == "__main__":
    asyncio.run(main())
