import structlog
from app.config import settings
from app.database.session import engine, Base
# আপনার প্রজেক্টের সব মডেল এখানে ইম্পোর্ট করতে হবে যাতে টেবিল ক্রিয়েট হয়
# উদাহরণস্বরূপ: from app.database.models import User, Task

logger = structlog.get_logger(__name__)

async def init_db():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            # ডেটাবেজের সব টেবিল একসাথে ক্রিয়েট করার জন্য
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(init_db())

