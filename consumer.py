"""Worker module for processing conversational astrology tasks.

Consumes tasks from Event Hub, processes them, and sends results back.
"""
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient
from azure.eventhub import EventData

from src.utils.logger import logger as log
from src.utils.redis_client import RedisClient
from src.utils.language_model import generate_reading
from config import Config

# Load environment variables
load_dotenv()

CONSUMER_GROUP = "$Default"

if not Config.EVENTHUB_CONN_STR or not Config.EVENTHUB_NAME:
    raise ValueError("Missing required environment variables: CONNECTION_STR and EVENT_HUB_NAME must be set.")


class ConversationalAstrologyWorker:
    def __init__(self):
        self.redis_client = None

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await RedisClient.create()
        log.info("ConversationalAstrologyWorker initialized")

    async def process_conversation_task(self, task_data: dict):
        """Process a conversational astrology task."""
        correlation_id = task_data.get("correlation_id")
        user_id = task_data.get("user_id")
        user_message = task_data.get("user_message")
        
        if not all([correlation_id, user_id, user_message]):
            log.error(f"Invalid task data: {task_data}")
            return None

        try:
            log.info(f"Processing conversational task {correlation_id} for user {user_id}")
            
            # Check if task is still pending using Redis
            status = await self.redis_client.get_status(correlation_id)
            if status != "pending":
                log.warning(f"Task {correlation_id} is no longer pending (status: {status})")
                return None

            # Generate conversational response using context
            response = await generate_reading(user_message, user_id, self.redis_client)
            
            # Create result payload
            result_payload = {
                "correlation_id": correlation_id,
                "user_id": user_id,
                "status": "completed",
                "result": response,
                "completed_at": datetime.utcnow().isoformat(),
                "type": "conversational_astrology_result"
            }
            
            return result_payload
            
        except Exception as e:
            log.error(f"Error processing task {correlation_id}: {e}")
            
            # Send error result
            error_payload = {
                "correlation_id": correlation_id,
                "user_id": user_id,
                "status": "error",
                "result": "Sorry, I'm having trouble responding right now. Please try again in a moment.",
                "completed_at": datetime.utcnow().isoformat(),
                "type": "conversational_astrology_result"
            }
            return error_payload

    async def on_event(self, partition_context, event):
        """Process incoming task events from Event Hub."""
        try:
            event_data = json.loads(event.body_as_str())
            correlation_id = event_data.get("correlation_id")
            
            # Only process conversational astrology tasks that are pending
            if (event_data.get("type") == "conversational_astrology" and 
                event_data.get("status") == "pending" and 
                await self.redis_client.is_pending(correlation_id)):
                
                log.info(f"Processing conversational task: {correlation_id}")

                # Process the task
                result = await self.process_conversation_task(event_data)
                
                if result:
                    # Send result back to Event Hub
                    producer = EventHubProducerClient.from_connection_string(
                        conn_str=Config.EVENTHUB_CONN_STR,
                        eventhub_name=Config.EVENTHUB_NAME
                    )
                    async with producer:
                        event_data_batch = await producer.create_batch()
                        event_data_batch.add(EventData(json.dumps(result)))
                        await producer.send_batch(event_data_batch)
                        log.info(f"Sent processed event for {correlation_id}")

                    # Update Redis status
                    if result["status"] in ["completed", "error"]:
                        await self.redis_client.set_result(correlation_id, result["result"])
                
                await partition_context.update_checkpoint(event)
            else:
                log.info(f"Skipping event: Not a pending conversational request or invalid correlation_id: {correlation_id}")

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse event data: {e}")
        except Exception as e:
            log.error(f"Error processing event: {e}")

    async def main(self):
        """Start the worker main loop."""
        await self.initialize()
        
        consumer_client = EventHubConsumerClient.from_connection_string(
            conn_str=Config.EVENTHUB_CONN_STR,
            consumer_group=CONSUMER_GROUP,
            eventhub_name=Config.EVENTHUB_NAME
        )

        async with consumer_client:
            await consumer_client.receive(
                on_event=self.on_event,
                starting_position="-1"
            )


def run_worker():
    """Start the conversational astrology worker."""
    worker = ConversationalAstrologyWorker()
    try:
        asyncio.run(worker.main())
    except ValueError as ve:
        log.error(f"Configuration error: {str(ve)}")
    except Exception as e:
        log.error(f"Failed to run consumer: {str(e)}")


if __name__ == "__main__":
    run_worker()