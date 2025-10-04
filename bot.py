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
import re
    
# Conversation states
WAITING_FOR_DOB = 1

# Global Redis client
redis_client = None


async def init_redis():
    """Initialize Redis client"""
    global redis_client
    redis_client = await RedisClient.create()


def _parse_dob_arg(arg: str) -> str:
    """Validate and normalize a date argument in YYYY-MM-DD format.

    Raises ValueError on invalid input.
    """
    normalized = arg.replace('/', '-')
    from datetime import datetime
    dt = datetime.fromisoformat(normalized)
    return dt.date().isoformat()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle `/start` command - asks user for date of birth."""
    welcome_text = (
        "🌟 Welcome to AstroBot! 🌟\n\n"
        "I can provide you with a personalized astrology reading based on your date of birth.\n\n"
        "Please send me your date of birth in one of these formats:\n"
        "• YYYY-MM-DD (e.g., 1990-05-23)\n"
        "• YYYY/MM/DD (e.g., 1990/05/23)"
    )
    await update.message.reply_text(welcome_text)
    return WAITING_FOR_DOB


async def handle_dob_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date of birth input from user."""
    user_message = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    try:
        dob = _parse_dob_arg(user_message)
        
        # Generate unique correlation ID
        correlation_id = str(uuid.uuid4())
        
        # Create task payload
        task_payload = {
            "correlation_id": correlation_id,
            "user_id": user_id,
            "dob": dob,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "astrology_reading",
            "status": "pending"
        }
        
        # Store pending task in Redis
        await redis_client.set_pending(
            correlation_id, 
            str(task_payload), 
            ttl=300  # 5 minutes TTL
        )
        
        # Send task to Event Hub
        await send_event(task_payload)
        
        await update.message.reply_text(
            "🔮 Generating your astrology reading... This may take a few seconds."
        )
        
        log.info(f"Dispatched task {correlation_id} for user {user_id} with DOB {dob}")

        # Start monitoring for completion (non-blocking)
        asyncio.create_task(
            monitor_task_completion(correlation_id, update, context)
        )
        
        return WAITING_FOR_DOB
        
    except ValueError as e:
        log.error(f"Invalid date format: {e}")
        await update.message.reply_text(
            "I couldn't understand that as a date. Please use YYYY-MM-DD or YYYY/MM/DD format.\n"
            "Example: 1990-05-23 or 1990/05/23\n\n"
            "Please try again:"
        )
        return WAITING_FOR_DOB
    except Exception as e:
        log.error(f"Failed to process DOB input: {e}")
        await update.message.reply_text(
            "Sorry, I encountered an error processing your request. Please try again."
        )
        return WAITING_FOR_DOB


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
                    await update.message.reply_text(
                        f"🌟 Your Astrology Reading 🌟\n\n{result}\n\n"
                        "Would you like another reading? Just send me another date!"
                    )
                    return
                else:
                    await update.message.reply_text(
                        "Sorry, I couldn't generate your reading. Please try again with another date."
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
        "Sorry, the reading generation took too long. Please try again with /start"
    )


async def handle_other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle other messages that are not DOB inputs."""
    user_message = update.message.text.strip()
    
    log.info(f"Received non-DOB message: {user_message}")

    if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}$', user_message):
        # Treat as DOB input
        return await handle_dob_input(update, context)

    response_text = (
        "I'd love to give you an astrology reading! 🌟\n\n"
        "Please send me your date of birth in YYYY-MM-DD format.\n"
        "Example: 1990-05-23 or 1990/05/23"
    )
    log.info("Prompting user for DOB")

    await update.message.reply_text(response_text)
    return WAITING_FOR_DOB


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    await update.message.reply_text(
        "Okay! If you want an astrology reading later, just send /start anytime! 🌟"
    )
    return ConversationHandler.END


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
    
    # Set up conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            WAITING_FOR_DOB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dob_input)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other_messages))
    
    log.info("Starting AstroBot Telegram bot with Event Hub integration")
    app.run_polling()