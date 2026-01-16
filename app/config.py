"""
Configuration module for Bozloader.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path


class Config:
    """Application configuration from environment variables."""
    
    # Application Settings
    APP_NAME = os.getenv('APP_NAME', 'Bozloader')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-to-a-random-secret-key')
    
    # Upload Instructions (customizable text shown on upload page)
    UPLOAD_INSTRUCTIONS_MOVIES = os.getenv(
        'UPLOAD_INSTRUCTIONS_MOVIES',
        'Upload your movie files here. Please name files: MovieTitle (Year).ext\n'
        'Example: Inception (2010).mkv'
    )
    
    UPLOAD_INSTRUCTIONS_TV = os.getenv(
        'UPLOAD_INSTRUCTIONS_TV',
        'Upload your TV show files here. Please name files: ShowName - S01E01.ext\n'
        'Example: Breaking Bad - S01E01.mkv'
    )
    
    # Storage Paths
    PENDING_MOVIES_PATH = os.getenv('PENDING_MOVIES_PATH', '/data/pending/movies')
    PENDING_TV_PATH = os.getenv('PENDING_TV_PATH', '/data/pending/tv')
    PLEX_MOVIES_PATH = os.getenv('PLEX_MOVIES_PATH', '/data/plex/movies')
    PLEX_TV_PATH = os.getenv('PLEX_TV_PATH', '/data/plex/tv')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/database/bozloader.db')
    
    # Admin Configuration
    ADMIN_EMAILS = [
        email.strip() 
        for email in os.getenv('ADMIN_EMAILS', 'admin@example.com').split(',')
        if email.strip()
    ]
    
    # Email Configuration (SMTP)
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'noreply@example.com')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() in ('true', '1', 'yes')
    
    # Email Feature Toggle
    EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'True').lower() in ('true', '1', 'yes')
    
    # Discord Configuration (Optional)
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
    DISCORD_ENABLED = bool(os.getenv('DISCORD_WEBHOOK_URL', ''))
    
    # Plex Configuration
    PLEX_URL = os.getenv('PLEX_URL', 'http://localhost:32400')
    PLEX_TOKEN = os.getenv('PLEX_TOKEN', '')
    PLEX_MOVIES_LIBRARY = os.getenv('PLEX_MOVIES_LIBRARY', 'Movies')
    PLEX_TV_LIBRARY = os.getenv('PLEX_TV_LIBRARY', 'TV Shows')
    PLEX_ENABLED = bool(os.getenv('PLEX_TOKEN', ''))
    
    # Upload Settings
    MAX_CONTENT_LENGTH = None  # No file size limit by default
    
    # App URL (for links in emails)
    APP_URL = os.getenv('APP_URL', 'http://localhost:8082')
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        
        # Check required paths exist or can be created
        for path_name in ['PENDING_MOVIES_PATH', 'PENDING_TV_PATH']:
            path = getattr(cls, path_name)
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create {path_name}: {e}")
        
        # Check database directory
        db_dir = Path(cls.DATABASE_PATH).parent
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create database directory: {e}")
        
        return errors
