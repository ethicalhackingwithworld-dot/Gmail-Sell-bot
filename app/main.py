"""
Main Application Entry Point
Initializes and runs the Telegram bot
"""

import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import structlog

from app.config import settings
from app.database.session import init_db, close_db
from app.handlers.start_handler import router as start_router
from app.handlers.task_handler import router as task_router
from app.middlewares.anti_flood import AntiFloodMiddleware, CallbackAntiFloodMiddleware

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def setup_storage():
    """Setup FSM storage based on environment"""
    try:
        if settings.ENVIRONMENT == "development":
            logger.info("Using MemoryStorage for development")
            return MemoryStorage()
        else:
            # Try Redis, fallback to Memory
            try:
                redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
                storage = RedisStorage.from_url(redis_url)
                logger.info("Using RedisStorage for production")
                return storage
            except Exception as e:
                logger.warning(f"Redis not available, using MemoryStorage: {e}")
                return MemoryStorage()
    except Exception as e:
        logger.error(f"Storage setup error: {e}")
        return MemoryStorage()


async def main():
    """Main function to start the bot"""
    try:
        logger.info("Starting Micro Task Platform Bot...")
        
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize bot
        bot = Bot(
            token="8699947886:AAGGEXPV918jpC_bumdjunCvdAr0vfKYZNI",
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Setup storage
        storage = await setup_storage()
        
        # Initialize dispatcher
        dp = Dispatcher(storage=storage)
        
        # Register middlewares
        dp.message.middleware(AntiFloodMiddleware(delay=0.5, max_messages_per_minute=30))
        dp.callback_query.middleware(CallbackAntiFloodMiddleware(delay=0.3))
        
        # Register routers
        dp.include_router(start_router)
        dp.include_router(task_router)
        
        logger.info(
            "Bot starting",
            bot_username=settings.Gmail_Sell_Shop_bot,
            environment=settings.ENVIRONMENT,
            debug=settings.DEBUG,
        )
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await close_db()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
