import logging
import os

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename='logs/test.log', level=logging.DEBUG)
logging.info("Test log")
print("Test print")
