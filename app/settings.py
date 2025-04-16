from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import datetime
class Settings(BaseSettings):

    POSTGRES_USER : str
    POSTGRES_PASSWORD : str
    POSTGRES_HOST : str
    POSTGRES_PORT : str
    POSTGRES_SYMBOLSERVICEDB : str

    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_MAX: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    REDIS_HOST : str
    REDIS_PORT : int
    REDIS_DB: int = 0

    CELERY_QUEUE: str = "tick_queue"
    CELERY_ROUTING_KEY: str = "tick_routing_key"
    CELERY_EXCHANGE: str = "tick_exchange"

    CELERY_DEFAULT_QUEUE: str = "default_queue"
    
    CELERY_TOKYO_STOCK_QUEUE: str = "tokyo_stock_queue"
    CELERY_TOKYO_STOCK_ROUTING_KEY: str = "tokyo_stock_routing_key"
    CELERY_TOKYO_STOCK_EXCHANGE: str = "tokyo_stock_exchange"
    CELERY_RETRIES_TIME: int = 5

    WEBSOCKET_API_KEY: str = "test"
    WEBSOCKET_HOST: str = "localhost:8000"

    JWT_SECRET_KEY : str
    JWT_REFRESH_SECRET_KEY : str

    SENDGRID_API_KEY : str
    MAIL_ADDRESS : str
    ENABLED_SEND_MAIL : bool = True

    BLOB_ACCOUNT_NAME : str
    BLOB_ACCOUNT_KEY : str
    
    PASSWORD_RESET_LINK : str

    ALLOW_ORIGINS: list[str] = ["*"]

    ENABLE_SCHEDULER: bool = True

    @property
    def DB_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_SYMBOLSERVICEDB}"
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"
    
    @property
    def BLOB_CONNECTION_STRING(self) -> str:
        return f"DefaultEndpointsProtocol=https;AccountName={self.BLOB_ACCOUNT_NAME};AccountKey={self.BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net"

settings = Settings()
