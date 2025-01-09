import logging

from dotenv import dotenv_values
env_config = dotenv_values(".env")


# Create a logger
logger = logging.getLogger(__name__)

# Set the logging level
logger.setLevel(env_config.get('LOG_LEVEL', 'DEBUG'))

# Create a file handler and set the log file path
file_handler = logging.StreamHandler()

# Create a formatter and set the format of log messages
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)
