# This module only serves to expose set_log_level,setup_logging, and get_filehandler
import logging
from .core.jslogging import logs, console_handler, dt_fmt


def set_log_level(level):
    """
    Sets the log level for both the logs and console handler to a given level.

    Args:
        level (int): The desired logging level.
    """
    logs.setLevel(level)
    console_handler.setLevel(logs.level)


def setup_logging(level: int, handler: logging.Handler = None):
    """
    This function sets up logging with the given level and handler. If no handler is provided, a file handler is generated.

    Args:
        level (int): The logging level to be set.
        handler (logging.Handler, optional): The handler to be used for logging. If no handler is provided, the function will generate a file handler.

    """

    logs.setLevel(level)
    if handler is not None:
        logs.addHandler(handler)


def get_filehandler(
    filename: str = "asyncjs.log",
    max_bytes: int = 8000000,
    file_count: int = 1,
    log_level: int = None,
):
    """
    This function creates a file handler for logging with the specified filename, maximum number
    of bytes for each file, and the number of files to rotate through.

    Args:
        filename (str, optional): The name of the file to write logs to. Defaults to "asyncjs.log".
        max_bytes (int, optional): The maximum size of each log file in bytes. Defaults to 8000000.
        file_count (int, optional): The number of log files to rotate through. Defaults to 1.
        log_level (int, optional): specific Log Level you want to set the handler to.
    Returns:
        handler2: A logging handler configured to write to the specified file, with the specified
        maximum file size, and rotating through the specified number of files.
    """
    handler2 = logging.handlers.RotatingFileHandler(
        filename=filename,
        encoding="utf-8",
        maxBytes=max_bytes,
        backupCount=file_count,  # Rotate through 5 files
    )
    # dt_fmt = "%Y-%m-%d %H:%M:%S"
    if log_level is not None:
        handler2.setLevel(log_level)
    formatter2 = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", dt_fmt)
    handler2.setFormatter(formatter2)
    return handler2
