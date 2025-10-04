"""Event Hub utility helpers with enhanced functionality."""
from typing import Callable, Awaitable, Any
import json
from azure.eventhub.aio import EventHubProducerClient, EventHubConsumerClient
from azure.eventhub import EventData
from src.utils.logger import logger as log
from config import Config


def ensure_configured():
    """Raise ValueError if EventHub configuration is missing."""
    if not Config.EVENTHUB_CONN_STR or not Config.EVENTHUB_NAME:
        raise ValueError("Missing required Event Hub configuration")


def create_producer() -> EventHubProducerClient:
    """Create and return an EventHubProducerClient."""
    ensure_configured()
    return EventHubProducerClient.from_connection_string(
        conn_str=Config.EVENTHUB_CONN_STR, 
        eventhub_name=Config.EVENTHUB_NAME
    )


def create_consumer(consumer_group: str = "$Default") -> EventHubConsumerClient:
    """Create and return an EventHubConsumerClient."""
    ensure_configured()
    return EventHubConsumerClient.from_connection_string(
        conn_str=Config.EVENTHUB_CONN_STR, 
        consumer_group=consumer_group, 
        eventhub_name=Config.EVENTHUB_NAME
    )


async def send_event(payload: dict[str, Any]):
    """Send a single event (payload) to Event Hub."""
    producer = create_producer()
    try:
        async with producer:
            batch = await producer.create_batch()
            event_data = EventData(json.dumps(payload))
            batch.add(event_data)
            await producer.send_batch(batch)
            log.debug(f"Sent EventHub event: {payload.get('type', 'unknown')} - {payload.get('correlation_id', 'unknown')}")
    except Exception as e:
        log.error(f"Failed to send event: {e}")
        raise


async def run_consumer(on_event: Callable[[Any, Any], Awaitable[None]], consumer_group: str = "default", starting_position: str = "-1"):
    """Run a consumer that calls `on_event(partition_context, event)` for each event."""
    consumer = create_consumer(consumer_group=consumer_group)
    async with consumer:
        await consumer.receive(
            on_event=on_event, 
            starting_position=starting_position,
            max_wait_time=5
        )