from redis import Redis, ConnectionPool
from app.settings import settings


redis_pool = ConnectionPool(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
redis_client = Redis(connection_pool=redis_pool)