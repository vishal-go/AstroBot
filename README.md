
# AstroBot

AstroBot is a conversational astrology assistant that runs as a Telegram bot. It uses an LLM (via OpenRouter), Azure Event Hubs for task streaming, and Redis for lightweight task coordination and conversation history.

This repository contains a simple worker (`consumer.py`) that processes tasks from Event Hub and a Telegram bot (`app.py` / `src/telegram/bot.py`) that enqueues user messages and returns results.

## Features

- Conversational astrology responses with contextual history
- Asynchronous task queueing using Azure Event Hub
- Redis-backed task state and conversation storage
- Separate worker process for scalable processing

## Requirements

- Python 3.11+ recommended
- Windows/macOS/Linux supported
- Redis instance (hosted or local)
- Azure Event Hub namespace and event hub
- Telegram bot token

Install dependencies from `requirements.txt` (preferably inside a virtual environment):

```powershell
# Create venv (Windows PowerShell)
python -m venv env
env\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Copy `example.env` to `.env` and fill in the required values, or set environment variables directly.

Required variables (in `.env` or environment):

- `TELEGRAM_BOT_TOKEN` - Telegram Bot API token
- `OPENROUTER_API_KEY` - API key for the LLM provider (OpenRouter-compatible)
- `DEFAULT_LLM_MODEL` - Optional: default model to request from the LLM
- `REDIS_URL` - Redis connection string (e.g. `redis://user:pass@host:port`)
- `CONNECTION_STR` - Azure Service Bus / Event Hub connection string
- `EVENT_HUB_NAME` - Event Hub name

The repository already includes a `.env` file for quick local testing; be sure to replace sensitive values with your own and do not commit secrets.

## Running the Telegram bot (development)

Start the bot which listens for Telegram messages and enqueues tasks:

```powershell
# Ensure your virtual env is activated
python app.py
```

The bot uses `src/telegram/bot.py` and will register handlers for `/start` and user messages.

## Running the worker

The worker listens to Event Hub for tasks, generates responses using the LLM, and writes results back (also via Event Hub/Redis depending on configuration):

```powershell
python consumer.py
```

Run the worker in a separate terminal or server (it uses `asyncio.run`).

## Development notes

- Logging is configured in `src/utils/logger.py` and writes to stdout.
- Redis helper is at `src/utils/redis_client.py`.
- Event Hub helpers are at `src/utils/eventhub_utils.py`.
- Conversational logic and LLM integration is implemented in `src/utils/language_model.py`.

## Troubleshooting

- If the bot doesn't start, confirm `TELEGRAM_BOT_TOKEN` is set and valid.
- If Event Hub code raises configuration errors, check `CONNECTION_STR` and `EVENT_HUB_NAME`.
- For Redis connection issues, verify `REDIS_URL` and that the Redis instance is reachable from your environment.

Useful debugging tips:

- Tail logs in the console; increase logging to DEBUG in `src/utils/logger.py` by setting `logger.setLevel(logging.DEBUG)`.
- Use `redis-cli` or a GUI Redis client to inspect keys like `task:<correlation_id>`.

## Security

- Keep API keys and tokens out of source control. Use environment variables or a secrets manager.
- The included `.env` is for local testing only and is listed in `.gitignore`.

## Contributing

Issues and pull requests welcome. Follow the standard GitHub flow and include tests for new logic where appropriate.

## License

MIT License — see `LICENSE`.

