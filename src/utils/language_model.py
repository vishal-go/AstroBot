"""Astrology reading generator for AstroBot.

This module provides a deterministic astrology reading based on a user's
date-of-birth (YYYY-MM-DD). If an OpenRouter/OpenAI API key is available the
module can also enrich the reading with the remote LLM; otherwise it falls back
to a local template-based generator. The goal is to keep the behaviour
predictable and testable.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from config import Config
from src.utils.logger import logger as log
import calendar
import httpx

async def generate_reading(dob: str, name: Optional[str] = None) -> str:
    """Produce an astrology reading for the given date-of-birth.

    If an OpenRouter API key is configured, the function will attempt to
    call the LLM to expand the local template; otherwise it returns a
    deterministic template-based reading. The output is a short paragraph.
    """
    # Attempt to enrich with LLM when API key is present
    if Config.OPENROUTER_API_KEY:
        log.info("Enriching reading via LLM")
        system_prompt = (
            "You are a friendly astrology assistant. Given a person's name (optional) "
            "and their sun sign, write a concise, empathetic astrology paragraph (3-5 sentences) "
            "that highlights personality traits, one practical tip and a short affirmation."
        )
        user_text = f"Name: {name or 'N/A'}\nProvide the reading."
        payload = {"model": Config.DEFAULT_LLM_MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                headers = {"Authorization": f"Bearer {Config.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
                resp = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [])[0].get("message", {}).get("content")
                if content:
                    return content
        except Exception as e:
            log.error(f"LLM enrichment failed, falling back to template: {e}")
    return "We're sorry, but we couldn't generate your astrology reading at this time."
