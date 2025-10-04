# AstroBot - Scalable Telegram Summarizer
AstroBot is a Telegram-based astrology service that produces short
astrology readings from a user's date-of-birth. The project includes:
This README explains how to configure, run and extend the project.

Getting started
---------------
1. Create a virtual environment and install dependencies:

```pwsh
python -m venv env
2. Create a `.env` file at the project root (or use `example.env`) with the
	 required environment variables (see below).

3. Start the Telegram bot:
```pwsh
python app.py
```
Configuration (environment variables)
-------------------------------------

Use a `.env` file or export environment variables in your process. Key
- TELEGRAM_BOT_TOKEN (required) — your Telegram Bot API token.
- REDIS_URL (required) — Redis connection URL. Examples:
	- redis://localhost:6379/0
- OPENROUTER_API_KEY (optional) — API key to enrich readings via OpenRouter
	/ OpenAI-compatible APIs.
- DEFAULT_LLM_MODEL (optional) — model id used when calling the LLM.
- CONNECTION_STR, EVENT_HUB_NAME (optional) — Azure Event Hub config used by
	the optional worker and event utilities.

How it works
- The Telegram bot asks the user for a date of birth and creates a task with
	a `correlation_id` saved in Redis as `task:<correlation_id>` with status
	`pending`.
- The bot publishes the task to Event Hub (if configured) or you can run a
	local worker (`consumer.py`) that polls Event Hub, processes tasks by
	generating a reading (via `src/utils/language_model.py`) and stores the
- The bot monitors Redis for completion and sends the reading to the user.

License
-------
This project is released under the MIT License. See the `LICENSE` file for details.
