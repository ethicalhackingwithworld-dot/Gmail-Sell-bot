"""
Application Configuration
Environment variables and settings management
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import json


class Settings(BaseSettings):
    """Main application settings"""
    
    # Bot Configuration
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token from @BotFather")
    BOT_USERNAME: str = Field(..., description="Bot username without @")
    
    # Database Configuration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        description="Async database URL"
    )
    DATABASE_URL_SYNC: str = Field(
        default="sqlite:///./bot.db",
        description="Sync database URL for Alembic"
    )
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis server host")
    REDIS_PORT: int = Field(default=6379, description="Redis server port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    
    # Admin Configuration
    ADMIN_IDS: str = Field(default="[]", description="JSON list of admin user IDs")
    
    @property
    def admin_ids(self) -> List[int]:
        """Parse admin IDs from JSON string"""
        try:
            return json.loads(self.ADMIN_IDS)
        except:
            return []
    
    # Security
    SECRET_KEY: str = Field(
        default="change-this-in-production",
        description="Secret key for encryption"
    )
    
    # Application
    ENVIRONMENT: str = Field(default="development", description="Environment mode")
    DEBUG: bool = Field(default=True, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    # Task Settings
    TASK_CLAIM_TIMEOUT_MINUTES: int = Field(
        default=30,
        description="Task claim timeout in minutes"
    )
    MAX_ACTIVE_CLAIMS_PER_USER: int = Field(
        default=5,
        description="Maximum active claims per user"
    )
    
    # Withdrawal Settings
    MIN_WITHDRAWAL_AMOUNT: float = Field(
        default=100,
        description="Minimum withdrawal amount in BDT"
    )
    MAX_WITHDRAWAL_AMOUNT: float = Field(
        default=25000,
        description="Maximum single withdrawal amount"
    )
    DAILY_WITHDRAWAL_LIMIT: float = Field(
        default=50000,
        description="Maximum daily withdrawal"
    )
    
    # Referral Settings
    REFERRAL_COMMISSION_PERCENT: float = Field(
        default=10,
        description="Default referral commission percentage"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
