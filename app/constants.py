from app.settings import settings
from datetime import datetime

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 3 
JWT_ALGORITHM = "HS256"

OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 2
PASSWORD_RESET_EXPIRE_MINUTES = 60

SNAPSHOT_BLOB_CONTAINER = "snapshots"
GENERAL_SNAPSHOT_URL = f"https://{settings.BLOB_ACCOUNT_NAME}.blob.core.windows.net/{SNAPSHOT_BLOB_CONTAINER}/"

TOKYO_STOCK_BLOB_CONTAINER= "tokyostock"
GENERAL_TOKYO_STOCK_URL = f"https://{settings.BLOB_ACCOUNT_NAME}.blob.core.windows.net/{TOKYO_STOCK_BLOB_CONTAINER}/"

PERIOD_LIST = [5, 10, 20, 50, 100]
BAR_TYPES = ["1d", "1w", "1m"]
PERIOD_PAIRS = [(5, 10), (5, 20), (5, 50), (5, 100), (10, 20), (10, 50), (10, 100), (20, 50), (20, 100), (50, 100)]

CLIENT_TIMEZONE = 9
TOKYO_STOCK_MAPPING = {
    "date": "日付",
    "exchange code": "取引所コード",
    "stock/bond type code": "株式債券種別ｺｰﾄﾞ",
    "security code": "銘柄コード",
    "isin": "ISIN",
    "morning session opening price": "前場始値",
    "morning session high price": "前場高値",
    "morning session low price": "前場安値",
    "morning session closing price": "前場終値",
    "afternoon session opening price": "後場始値",
    "afternoon session high price": "後場高値",
    "afternoon session low price": "後場安値",
    "afternoon session closing price": "後場終値",
    "all-day opening price": "日通し始値",
    "all-day high price": "日通し高値",
    "all-day low price": "日通し安値",
    "all-day closing price": "日通し終値",
    "special quote code": "特別気配コード",
    "special quote price": "特別気配値段",
    "settlement price / margin calculation standard price": "清算値段／証拠金算定基準値段",
    "trading volume": "売買高",
    "trading value": "売買代金",
    "vwap": "VWAP"
}
TOP_SYMBOLS = [
            'USDJPY', 'EURUSD', 'GBPUSD', 'EURJPY', 'GOLD', 'SILVER', 'Copper',
            'UKOil', 'USOil', 'JP225', 'HK50', 'US30', 'US100'
        ]