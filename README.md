# AstroBot - Scalable Telegram Summarizer
AstroBot is a Telegram-based astrology service that produces short
astrology readings from a user's date-of-birth. The project includes:

- A Telegram bot (`src/telegram/bot.py`) which accepts DOB input from users
	and coordinates reading generation.
- A Redis-backed task store (`src/utils/redis_client.py`) used to track
	pending/completed readings.
- Optional Event Hub helpers (`src/utils/eventhub_utils.py`) and a worker
	scaffold (`consumer.py`) for offloading reading generation.

This README explains how to configure, run and extend the project.

Getting started
---------------

1. Create a virtual environment and install dependencies:

```pwsh
python -m venv env
.\n+env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Create a `.env` file at the project root (or use `example.env`) with the
	 required environment variables (see below).

3. Start the Telegram bot:

```pwsh
python app.py
```

Configuration (environment variables)
-------------------------------------

Use a `.env` file or export environment variables in your process. Key
variables:

- TELEGRAM_BOT_TOKEN (required) — your Telegram Bot API token.
- REDIS_URL (required) — Redis connection URL. Examples:
	- redis://localhost:6379/0
	- redis://my-redis-host:14644
	If your REDIS_URL is just `host:port` the code will automatically prefix
	`redis://` for you.
- OPENROUTER_API_KEY (optional) — API key to enrich readings via OpenRouter
	/ OpenAI-compatible APIs.
- DEFAULT_LLM_MODEL (optional) — model id used when calling the LLM.
- CONNECTION_STR, EVENT_HUB_NAME (optional) — Azure Event Hub config used by
	the optional worker and event utilities.

How it works
------------

- The Telegram bot asks the user for a date of birth and creates a task with
	a `correlation_id` saved in Redis as `task:<correlation_id>` with status
	`pending`.
- The bot publishes the task to Event Hub (if configured) or you can run a
	local worker (`consumer.py`) that polls Event Hub, processes tasks by
	generating a reading (via `src/utils/language_model.py`) and stores the
	completed result back in Redis.
- The bot monitors Redis for completion and sends the reading to the user.

Running the worker (optional)
-----------------------------

If you want to offload reading generation to an asynchronous worker, run
`consumer.py` (it expects Event Hub configuration):

```pwsh
python consumer.py
```

If you don't use Event Hub, you can still call `generate_reading()` directly
from the bot (the project is flexible). The `language_model` supports a
template fallback when no LLM key is configured.

Troubleshooting
---------------

- aioredis errors: this project uses `redis.asyncio` (redis-py) — make sure
	`redis>=4.6.0` is installed. If you previously had `aioredis` installed,
	remove it to avoid conflicts.
- Redis URL errors: supply a proper URL in `.env`; `host:port` without
	scheme will be normalized automatically but prefer the full `redis://` URL.
- LLM timeouts: the language model client uses a timeout; check network
	connectivity and API key validity.

Developer notes
---------------

- Core files:
	- `src/telegram/bot.py` — main bot implementation
	- `src/utils/language_model.py` — reading generation (LLM + templates)
	- `src/utils/redis_client.py` — Redis helper
	- `src/utils/eventhub_utils.py` — small Event Hub convenience functions

- To add caching for user preferences, use `redis_client.store_token` or
	add new fields to the task hash.
- To extend astrology logic, update `src/utils/language_model.py` with more
	detailed templates or additional computed charts (requires astronomical
	libs for accuracy).

License & safety
----------------

This project is intended as an example scaffold. If you process user data
ensure you comply with local privacy laws and secure your API keys. Don't
commit `.env` containing secrets to source control — `.gitignore` already
excludes `.env`.

If you want, I can:
- Add a `docker-compose.yml` that runs Redis + the bot for local testing.
- Add a `/recent` command to fetch previous readings for a user from Redis.
- Add unit tests for DOB parsing and zodiac sign logic.

