import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str
    database: str
    user: str
    password: str
    port: int


@dataclass
class AppConfig:
    """Application configuration."""
    database: DatabaseConfig
    max_workers: int
    time_range_days: int
    bluesky_base_url: str
    log_level: str
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'AppConfig':
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file, override=True)
        else:
            load_dotenv(override=True)
        
        # Validate required environment variables
        required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        return cls(
            database=DatabaseConfig(
                host=os.getenv('DB_HOST'),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                port=int(os.getenv('DB_PORT', 5432))
            ),
            max_workers=int(os.getenv('MAX_WORKERS', 10)),
            time_range_days=int(os.getenv('TIME_RANGE_DAYS', 7)),
            bluesky_base_url=os.getenv('BLUESKY_BASE_URL', 'https://public.api.bsky.app'),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )


def setup_logging(log_level: str = 'INFO') -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('dopplersky.log')
        ]
    )
    
    # Set specific loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)