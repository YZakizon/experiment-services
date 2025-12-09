import logging
import sys
from contextvars import ContextVar
from middleware import RequestIDMiddleware

class ContextualFilter(logging.Filter):
    """A logging filter that injects the request ID from ContextVar."""
    def filter(self, record: logging.LogRecord) -> bool:
        # Get the current ID from the context
        record.request_id = RequestIDMiddleware.request_id_context().get()
        return True

# 3. Configure the Logger with the new filter and format
def setup_logging(log_level: str = "INFO", log_filename: str = "experiment_service.log"):
    log_filter = ContextualFilter()

    # The format must include the custom 'request_id' attribute
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(request_id)s] - %(name)s - %(message)s'
    )

    # Configure handler (e.g., console handler)
    stream_handler = logging.StreamHandler(sys.stdout)

    file_handler = logging.FileHandler(log_filename, mode='a')
    
    handlers=[
        # Handler to send logs to the console (standard output)
        stream_handler,
        # Handler to send logs to a file
        file_handler
    ]
    
    # set additional settings
    for handler in handlers:
        handler.addFilter(log_filter)
        handler.setFormatter(formatter)

    # Apply the handler to the root logger
    # TODO: get logging level from env
    logging.basicConfig(level=logging.getLevelName(log_level), handlers=handlers)

