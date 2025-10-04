"""Configuration module for AstroBot.

Loads environment variables and provides strongly named configuration values used
across the application.
"""
from dotenv import load_dotenv
import os

load_dotenv(override=True)


class Config:
    """Application configuration.

    Attributes:
        TELEGRAM_BOT_TOKEN: str | None - Telegram bot token
        OPENROUTER_API_KEY: str | None - Router/OpenAI compatible API key
        DEFAULT_LLM_MODEL: str - Default model identifier
        REDIS_URL: str - Redis connection URL
        EVENTHUB_CONN_STR: str | None - Azure Event Hub connection string
        EVENTHUB_NAME: str | None - Azure Event Hub name
    """
    print("Loading configuration from environment variables...")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    EVENTHUB_CONN_STR = os.getenv("CONNECTION_STR")
    EVENTHUB_NAME = os.getenv("EVENT_HUB_NAME")
