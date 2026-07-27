"""
Anti-Flood Middleware
Prevents spam and bot abuse with rate limiting
"""

import time
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import structlog

logger = structlog.get_logger(__name__)


class AntiFloodMiddleware(BaseMiddleware):
    """
    Middleware to prevent message flooding
    Implements rate limiting per user
    """
    
    def __init__(self, delay: float = 0.5, max_messages_per_minute: int = 30):
        """
        Initialize anti-flood middleware
        
        Args:
            delay: Minimum delay between messages in seconds
            max_messages_per_minute: Maximum messages allowed per minute
        """
        self.delay = delay
        self.max_messages_per_minute = max_messages_per_minute
        
        # Track last message time per user
        self.last_message_time: Dict[int, float] = {}
        
        # Track message count per minute per user
        self.message_count: Dict[int, Dict[str, int]] = {}
        
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process incoming message with rate limiting
        
        Args:
            handler: Next handler in chain
            event: Telegram message event
            data: Additional data
            
        Returns:
            Handler result or None if blocked
        """
        user_id = event.from_user.id if event.from_user else None
        
        if not user_id:
            return await handler(event, data)
        
        current_time = time.time()
        current_minute = time.strftime("%Y-%m-%d %H:%M")
        
        # Initialize tracking for new users
        if user_id not in self.message_count:
            self.message_count[user_id] = {
                "minute": current_minute,
                "count": 0,
            }
        
        # Reset counter for new minute
        if self.message_count[user_id]["minute"] != current_minute:
            self.message_count[user_id] = {
                "minute": current_minute,
                "count": 0,
            }
        
        # Check rate limits
        # 1. Delay between messages
        if user_id in self.last_message_time:
            time_diff = current_time - self.last_message_time[user_id]
            if time_diff < self.delay:
                # Too fast, silently ignore
                logger.warning(
                    f"Anti-flood: Message too fast",
                    user_id=user_id,
                    time_diff=time_diff,
                )
                return
        
        # 2. Messages per minute limit
        if self.message_count[user_id]["count"] >= self.max_messages_per_minute:
            logger.warning(
                f"Anti-flood: Rate limit exceeded",
                user_id=user_id,
                count=self.message_count[user_id]["count"],
            )
            
            # Notify user only once per minute
            if self.message_count[user_id]["count"] == self.max_messages_per_minute:
                try:
                    await event.answer(
                        "⚠️ আপনি খুব দ্রুত মেসেজ পাঠাচ্ছেন। দয়া করে একটু অপেক্ষা করুন।\n"
                        "⚠️ You're sending messages too fast. Please wait a moment."
                    )
                except:
                    pass
            
            return
        
        # Update tracking
        self.last_message_time[user_id] = current_time
        self.message_count[user_id]["count"] += 1
        
        # Process message
        return await handler(event, data)


class CallbackAntiFloodMiddleware(BaseMiddleware):
    """Rate limiting for callback queries"""
    
    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.last_callback_time: Dict[int, float] = {}
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        """Process callback with rate limiting"""
        user_id = event.from_user.id
        current_time = time.time()
        
        if user_id in self.last_callback_time:
            time_diff = current_time - self.last_callback_time[user_id]
            if time_diff < self.delay:
                try:
                    await event.answer(
                        "⏳ দয়া করে অপেক্ষা করুন...",
                        show_alert=False,
                    )
                except:
                    pass
                return
        
        self.last_callback_time[user_id] = current_time
        return await handler(event, data)
