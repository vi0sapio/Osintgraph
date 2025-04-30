import logging

# Import third-party libraries first (before configuring logging)
import neo4j
import instaloader

class CustomFormatter(logging.Formatter):
    """Custom log formatter with color coding for different log levels"""
    
    # ANSI escape codes for colors
    magenta = "\x1b[35;1m"
    green = "\x1b[32;1m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # Default log format
    time = "%(asctime)s "
    format = "[%(levelname)s]"
    message = " - %(message)s "

    # Dictionary for formatting based on log level
    FORMATS = {
        logging.DEBUG: time + magenta + format + reset + message,
        logging.INFO: time + green + format + reset + message,
        logging.WARNING: time + yellow + format + reset + message,
        logging.ERROR: time + red + format + reset + message,
        logging.CRITICAL: time + red + format + reset + red + message + reset
    }

    def format(self, record):
        """Override format method to apply custom formatting with colors"""
        log_fmt = self.FORMATS.get(record.levelno, self.format)  # Default to standard format
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

# Function to set up the root logger with debug_mode
def setup_root_logger(debug_mode=False):
    # Disable logging for specific libraries (after importing them)
    disable_library_loggers()

    """Set up the root logger with a custom formatter"""
    # Create or get the root logger
    logger = logging.getLogger()

    # Prevent adding handlers multiple times
    if not logger.hasHandlers():
        # Create a stream handler (for console output)
        handler = logging.StreamHandler()

        # Set the custom formatter for the handler
        formatter = CustomFormatter()
        handler.setFormatter(formatter)

        # Set the logging level based on debug_mode
        if debug_mode:
            logger.setLevel(logging.DEBUG)  # Enable DEBUG level if True
        else:
            logger.setLevel(logging.INFO)  # Enable INFO level if False

        # Add the handler to the root logger
        logger.addHandler(handler)

# Function to disable loggers from third-party libraries like neo4j and instaloader
def disable_library_loggers():
    """Disable logging for third-party libraries including neo4j and concurrency libraries."""
    # List of loggers to disable for neo4j and concurrency-related libraries
    logger_names = [
        "neo4j.auth_management",
        "neo4j.io",
        "neo4j.pool",
        "neo4j.notifications",
        "neo4j",
        "concurrent.futures",
        "concurrent",
        "asyncio",
        "urllib3.util.retry",
        "urllib3.util",
        "urllib3",
        "urllib3.connection",
        "urllib3.response",
        "urllib3.connectionpool",
        "urllib3.poolmanager",
        "charset_normalizer",
        "socks",
        "requests"
    ]
    
    # Disable each logger in the list
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        
        # Set log level to CRITICAL to suppress lower-level logs
        logger.setLevel(logging.CRITICAL)
        
        # Disable propagation (so that messages don't propagate to the root logger)
        logger.propagate = False

        # Remove all handlers attached to these loggers to ensure no logs are emitted
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

# Call this function during your logger setup

