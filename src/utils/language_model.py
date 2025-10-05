"""Conversational astrology assistant for AstroBot.

This module provides a conversational astrology assistant that maintains
context and provides personalized responses using LangChain.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import Config
from src.utils.logger import logger as log
import httpx
import json


class ConversationalAstrologyAssistant:
    def __init__(self):
        self.system_prompt = """You are AstroBot, a friendly and knowledgeable astrology assistant. You help users with:

1. Daily horoscopes and astrology readings
2. Zodiac sign interpretations and compatibility
3. Birth chart insights (if date of birth is provided)
4. General astrology questions and guidance

Always be:
- Empathetic and encouraging
- Specific and personalized when possible
- Clear about astrology concepts
- Respectful of different beliefs

If users don't provide their zodiac sign or birth date, ask politely for it to give more personalized readings.

Keep responses conversational and engaging, but focused. Limit responses to 3-5 sentences unless more detail is requested."""

    async def get_conversation_history(self, user_id: str, redis_client) -> List[Dict[str, str]]:
        """Get conversation history from Redis for a user."""
        try:
            history_key = f"conversation_history:{user_id}"
            history_data = await redis_client.get_attr(history_key, "messages")
            if history_data:
                return json.loads(history_data)
        except Exception as e:
            log.error(f"Error getting conversation history for {user_id}: {e}")
        return []

    async def save_conversation_history(self, user_id: str, messages: List[Dict[str, str]], redis_client):
        """Save conversation history to Redis with limit."""
        try:
            # Keep only last 10 messages to manage context length
            if len(messages) > 10:
                messages = messages[-10:]
            
            history_key = f"conversation_history:{user_id}"
            await redis_client.set_attr(
                history_key,
                "messages",
                json.dumps(messages)
            )
        except Exception as e:
            log.error(f"Error saving conversation history for {user_id}: {e}")

    async def generate_response(self, user_message: str, user_id: str, redis_client) -> str:
        """Generate a conversational response using context history."""
        try:
            # Get conversation history
            history = await self.get_conversation_history(user_id, redis_client)
            
            # Build messages for LLM
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for msg in history:
                messages.append(msg)
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Call LLM API
            response = await self._call_llm_api(messages)
            
            # Update conversation history
            history.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response}
            ])
            
            # Save updated history
            await self.save_conversation_history(user_id, history, redis_client)
            
            return response
            
        except Exception as e:
            log.error(f"Error generating conversational response: {e}")
            return "I apologize, but I'm having trouble generating a response right now. Please try again in a moment."

    async def _call_llm_api(self, messages: List[Dict[str, str]]) -> str:
        """Make API call to LLM service."""
        if not Config.OPENROUTER_API_KEY:
            return self._get_fallback_response(messages)
        
        try:
            payload = {
                "model": Config.DEFAULT_LLM_MODEL,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            async with httpx.AsyncClient(timeout=120) as client:
                headers = {
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/astrobot-app",  # Required by OpenRouter
                    "X-Title": "AstroBot"  # Required by OpenRouter
                }
                
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                
                content = data.get("choices", [])[0].get("message", {}).get("content")
                if content:
                    return content.strip()
                else:
                    raise ValueError("No content in response")
                    
        except Exception as e:
            log.error(f"LLM API call failed: {e}")
            return self._get_fallback_response(messages)

    def _get_fallback_response(self, messages: List[Dict[str, str]]) -> str:
        """Provide a fallback response when LLM is unavailable."""
        user_message = messages[-1]["content"].lower() if messages else ""
        
        astrology_keywords = ["horoscope", "zodiac", "birth", "chart", "astrology", "star", "sign"]
        if any(keyword in user_message for keyword in astrology_keywords):
            return "🌟 As an astrology assistant, I'd love to help you with your astrology questions! For personalized readings, please share your birth date (YYYY-MM-DD) or zodiac sign. 🔮"
        
        return "I'd be happy to help you with astrology-related questions! You can ask me about horoscopes, zodiac signs, birth charts, or anything else astrology-related. What would you like to know? 💫"


# Initialize global assistant instance
assistant = ConversationalAstrologyAssistant()


async def generate_reading(user_message: str, user_id: str, redis_client) -> str:
    """Generate a conversational astrology response."""
    return await assistant.generate_response(user_message, user_id, redis_client)
