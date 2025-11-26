import logging
import sys
from trading_bot.config import settings

def setup_logging():
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Logging configured.")

def get_logger(name: str):
    return logging.getLogger(name)
