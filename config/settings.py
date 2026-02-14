"""
Tovito Trader - Settings Module
================================

Usage:
    from config.settings import settings
    
    db_path = settings.DATABASE_PATH
    if settings.is_production:
        ...
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Settings:
    def __init__(self):
        self.ENV = os.getenv('TOVITO_ENV', 'development')
        
        # Try config folder first, then root
        config_dir = Path(__file__).parent
        env_file = config_dir / f'.env.{self.ENV}'
        if not env_file.exists():
            env_file = config_dir.parent / '.env'
        if env_file.exists():
            load_dotenv(env_file)
        
        # Database
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/tovito.db')
        self.ANALYTICS_DB_PATH = os.getenv('ANALYTICS_DB_PATH', 'analytics/analytics.db')
        
        # Tradier
        self.TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
        self.TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID')
        self.TRADIER_API_URL = os.getenv('TRADIER_API_URL', 'https://api.tradier.com/v1')
        
        # Email
        self.EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
        self.SMTP_USER = os.getenv('SMTP_USER', '')
        self.SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
        self.ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
        
        # Logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        
        # Business
        self.TAX_RATE = float(os.getenv('TAX_RATE', 0.37))
        self.HEALTHCHECK_URL = os.getenv('HEALTHCHECK_URL', '')
    
    @property
    def is_production(self): return self.ENV == 'production'
    
    @property
    def is_development(self): return self.ENV == 'development'
    
    @property
    def is_test(self): return self.ENV == 'test'


settings = Settings()
