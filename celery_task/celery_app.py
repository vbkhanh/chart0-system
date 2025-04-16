from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.settings import settings

celery_app = Celery("CSVProcess", broker=settings.REDIS_URL)

celery_app.conf.update(
    result_backend=settings.REDIS_URL,
    task_ignore_result=True,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    imports=(
        "celery_task.task",
        "celery_task.cronjob"
    ),
)

default_exchange = Exchange(settings.CELERY_TOKYO_STOCK_EXCHANGE, type="direct")

default_queue = Queue(
    settings.CELERY_DEFAULT_QUEUE,
    default_exchange,
    routing_key=settings.CELERY_TOKYO_STOCK_ROUTING_KEY
)

tokyo_stock_queue = Queue(
    settings.CELERY_TOKYO_STOCK_QUEUE,
    default_exchange,
    routing_key=settings.CELERY_TOKYO_STOCK_ROUTING_KEY
)

celery_app.conf.task_queues = (default_queue, tokyo_stock_queue,)

celery_app.conf.task_default_queue = settings.CELERY_DEFAULT_QUEUE
celery_app.conf.task_default_exchange = settings.CELERY_TOKYO_STOCK_EXCHANGE
celery_app.conf.task_default_routing_key = settings.CELERY_TOKYO_STOCK_ROUTING_KEY

celery_app.conf.beat_schedule = {
    'calculate_MA_task': {
        'task': 'calculate_MA_task',
        'schedule': crontab(hour=23, minute=30),
    },
    'generate_week_month_bars_from_tokyo_upload_task': {
        'task': 'generate_week_month_bars_from_tokyo_upload_task_for_all',
        'schedule': crontab(hour=23, minute=15),
    },
    # 'calculate_provisional_bars_for_tokyo_upload_task': {
    #     'task': 'get_stock_symbol_ids',
    #     'schedule': crontab(hour=9, minute=30),
    # },
}
