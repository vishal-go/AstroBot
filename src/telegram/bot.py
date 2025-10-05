"""Telegram bot for the AstroBot astrology application.

Enhanced with Event Hub and Redis for task coordination.
"""
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import asyncio
import uuid
from datetime import datetime
from config import Config
from src.utils.logger import logger as log
from src.utils.eventhub_utils import send_event, create_consumer
from src.utils.redis_client import RedisClient
import json
    
# Global Redis client
redis_client = None


async def init_redis():
    """Initialize Redis client"""
    global redis_client
    redis_client = await RedisClient.create()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle `/start` command - starts conversation with user."""
    welcome_text = (
        "🌟 Welcome to AstroBot! 🌟\n\n"
        "I'm your conversational astrology assistant! You can ask me about:\n"
        "• Your daily horoscope\n"
        "• Astrology readings\n"
        "• Zodiac sign insights\n"
        "• Or anything else astrology-related!\n\n"
        "Just send me a message and I'll help you! 🔮"
    )
    await update.message.reply_text(welcome_text)


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any user message and send to processing queue."""
    user_message = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    try:
        # Generate unique correlation ID
        correlation_id = str(uuid.uuid4())
        
        # Create task payload
        task_payload = {
            "correlation_id": correlation_id,
            "user_id": user_id,
            "user_message": user_message,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "conversational_astrology",
            "status": "pending"
        }
        
        # Store pending task in Redis
        await redis_client.set_pending(
            correlation_id, 
            json.dumps(task_payload), 
            ttl=300  # 5 minutes TTL
        )
        
        # Send task to Event Hub
        await send_event(task_payload)
        
        await update.message.reply_text(
            "💫 Thinking about your question... This may take a few seconds."
        )
        
        log.info(f"Dispatched conversational task {correlation_id} for user {user_id}")

        # Start monitoring for completion (non-blocking)
        asyncio.create_task(
            monitor_task_completion(correlation_id, update, context)
        )
        
    except Exception as e:
        log.error(f"Failed to process user message: {e}")
        await update.message.reply_text(
            "Sorry, I encountered an error processing your message. Please try again."
        )


async def monitor_task_completion(correlation_id: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monitor Redis for task completion and send result to user."""
    max_wait_time = 300  # 5 minutes max wait
    check_interval = 2   # Check every 2 seconds
    
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < max_wait_time:
        try:
            status = await redis_client.get_status(correlation_id)
            
            if status == "completed":
                result = await redis_client.get_result(correlation_id)
                if result:
                    await update.message.reply_text(result)
                    return
                else:
                    await update.message.reply_text(
                        "Sorry, I couldn't generate a response. Please try again with a different question."
                    )
                    return
            elif status == "pending":
                # Still processing, wait and check again
                await asyncio.sleep(check_interval)
            else:
                # Task not found or expired
                break
                
        except Exception as e:
            log.error(f"Error monitoring task {correlation_id}: {e}")
            await asyncio.sleep(check_interval)
    
    # Timeout or error
    await update.message.reply_text(
        "Sorry, the response generation took too long. Please try again with your question."
    )


async def start_result_consumer():
    """Start consuming completed results from Event Hub."""
    async def on_completed_event(partition_context, event):
        try:
            event_data = event.body_as_str()
            result_data = json.loads(event_data)
            
            correlation_id = result_data.get("correlation_id")
            status = result_data.get("status")
            result = result_data.get("result")
            
            if status == "completed" and correlation_id and result:
                # Store completed result in Redis
                await redis_client.set_result(correlation_id, result)
                log.info(f"Stored completed result for {correlation_id}")
                
        except Exception as e:
            log.error(f"Error processing completed event: {e}")
    
    # Start consumer in background
    asyncio.create_task(
        run_consumer_loop(on_completed_event, "bot_consumer")
    )


async def run_consumer_loop(on_event, consumer_group: str = "bot_consumer"):
    """Run consumer loop with reconnection logic."""
    while True:
        try:
            consumer = create_consumer(consumer_group=consumer_group)
            async with consumer:
                await consumer.receive(
                    on_event=on_event,
                    starting_position="-1",  # Latest events
                    max_wait_time=5  # seconds
                )
        except Exception as e:
            log.error(f"Consumer loop error: {e}, reconnecting in 10 seconds...")
            await asyncio.sleep(10)


def run_bot():
    """Start the Telegram bot with Redis and Event Hub integration."""
    if not Config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in environment")

    # Initialize Redis and start consumers
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_redis())
    loop.run_until_complete(start_result_consumer())

    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    
    log.info("Starting Conversational AstroBot Telegram bot with Event Hub integration")
    app.run_polling()