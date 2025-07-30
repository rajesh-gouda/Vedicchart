# logger.py

import logging
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Logger instance
logger = logging.getLogger("vedic_logger")
logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

# Formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s", "%Y-%m-%d %H:%M:%S"
)

# File Handler
file_handler = logging.FileHandler("logs/vedic.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Stream Handler (for Docker logs)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)

# Avoid adding handlers multiple times (especially in Docker reloads)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
