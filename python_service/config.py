"""
Configuration management for Ceph Tracker Linker service
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Base configuration"""
    
    # Flask settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Ceph Tracker settings
    CEPH_TRACKER_URL = os.getenv('CEPH_TRACKER_URL', 'https://tracker.ceph.com')
    CEPH_PROJECT_ID = os.getenv('CEPH_PROJECT_ID', '')
    
    # GitHub settings
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
    GITHUB_REPO = os.getenv('GITHUB_REPO', 'ceph/ceph')
    
    # Embedding Model settings (Sentence Transformers - no API key needed!)
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    # Options: 'all-MiniLM-L6-v2' (fast, 384 dim), 'all-mpnet-base-v2' (best quality, 768 dim)
    EMBEDDING_CACHE_DIR = os.getenv('EMBEDDING_CACHE_DIR', './models')
    
    # Recommendation settings
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.75'))
    MAX_RECOMMENDATIONS = int(os.getenv('MAX_RECOMMENDATIONS', '10'))
    
    # Cache settings
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour
    
    # Rate limiting
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '60'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'ceph_linker.log')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        # No API keys required for Sentence Transformers!
        # Just validate that model name is set
        if not cls.EMBEDDING_MODEL:
            errors.append("EMBEDDING_MODEL is required")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


class TestConfig(Config):
    """Test configuration"""
    DEBUG = True
    TESTING = True
    CACHE_TTL = 0  # Disable caching in tests


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration based on environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])

# Made with Bob
