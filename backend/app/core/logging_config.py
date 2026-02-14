"""
Logging configuration for Smart Scheduler
"""
import logging
import sys

def setup_logging(environment="production"):
    """Configure application logging"""
    log_level = logging.DEBUG if environment != "production" else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if environment != "production" else logging.WARNING
    )
    
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info(f"[LOGGING] Configured for environment: {environment}")
    
    return logger


# Create default logger
logger = logging.getLogger(__name__)
