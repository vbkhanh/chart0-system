import logging
from kombu import Connection, Exchange, Queue
from app.settings import settings
import json
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Create a connection to the broker
    with Connection(f"{settings.REDIS_URL}") as conn:
        logger.info(f"Data setting: {settings.model_dump()}")
        # Define the exchange
        exchange = Exchange(settings.CELERY_EXCHANGE, type="direct", durable=True)

        # Define the queue and bind it to the exchange
        queue = Queue(settings.CELERY_QUEUE, exchange, routing_key=settings.CELERY_ROUTING_KEY)
        queue.declare(channel=conn.channel())  # Declare the queue in the broker

        # Callback function to process messages
        def process_message(body, message):
            logger.info(f"Send data: {body}")
            headers = {'Content-Type': 'application/json'}
            data = json.dumps(body)
            response = requests.post(
                url=f"https://{settings.WEBSOCKET_HOST}/trigger/{body['symbol']}?token={settings.WEBSOCKET_API_KEY}",
                headers=headers,
                data=data
            )
            if response.status_code != 200:
                logger.error(f"Failed to send message: {response.status_code} - {response.text}")
            # Acknowledge the message so it’s removed from the queue
            message.ack()

        # Start consuming messages
        with conn.Consumer(queue, callbacks=[process_message], accept=["json"]) as consumer:
            logger.info("Waiting for messages...")
            while True:
                conn.drain_events()  # Wait for messages

if __name__ == "__main__":
    try:
        logger.info("Consumer is running. Press Ctrl+C to exit.")
        main()
    except KeyboardInterrupt:
        logger.info("Consumer stopped.")
