import inspect
import logging
import os

"""
a simple logger.
"""

logs = logging.getLogger("asyncjs")
logs.setLevel(logging.ERROR)

# Create a console handler and set the level to Debug
console_handler=logging.StreamHandler()
#console_handler = logging.FileHandler("asyncjs.log")
#console_handler.setLevel(logs.getLevel())

# Create a formatter and add it to the console handler
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", dt_fmt)
console_handler.setFormatter(formatter)

# Add the console handler to the logs
logs.addHandler(console_handler)
def setup_logging(level:int, handler:logging.Handler=None):
    """
    This function sets up logging with the given level and handler. If no handler is provided, a file handler is generated.

    Args:
        level (int): The logging level to be set.
        handler (logging.Handler, optional): The handler to be used for logging. If no handler is provided, the function will generate a file handler.

    """

    logs.setLevel(level)
    if handler is None:
        handler=get_filehandler()
    logs.addHandler(handler)

    
def get_filehandler(filename:str="asyncjs.log",max_bytes:int=8000000,file_count:int=1):
    """
    This function creates a file handler for logging with the specified filename, maximum number
    of bytes for each file, and the number of files to rotate through.

    Args:
        filename (str, optional): The name of the file to write logs to. Defaults to "asyncjs.log".
        max_bytes (int, optional): The maximum size of each log file in bytes. Defaults to 8000000.
        file_count (int, optional): The number of log files to rotate through. Defaults to 1.

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
    formatter2 = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", dt_fmt)
    handler2.setFormatter(formatter2)
    return handler2



def log_error(*args, **kwargs):
    if logs is not None:
        logs.error(*args, **kwargs)

def log_info(*args, **kwargs):
    if logs is not None:
        logs.info(*args, **kwargs)

def log_warning(*args, **kwargs):
    if logs is not None:
        logs.warning(*args, **kwargs)

def log_debug(*args, **kwargs):
    if logs is not None:
        logs.debug(*args, **kwargs)



def log_print(*msg):
    logs.info(str(msg))


def set_log_level(level):
    logs.setLevel(level)
    console_handler.setLevel(logs.level)


def print_path(frame):
    output = "now"
    for _ in range(5):
        clsv = ""
        if "self" in frame.f_locals:
            instance = frame.f_locals["self"]
            if hasattr(instance, "__class__"):
                clsv = instance.__class__.__name__ + "."
        filename = os.path.basename(frame.f_code.co_filename)
        output = f"{output}->[[{filename}].{clsv}{frame.f_code.co_name}]"
        if frame.f_back is not None:
            frame = frame.f_back
        else:
            break
    return output


def print_path_depth(depth=2):
    frame = inspect.currentframe()
    for d in range(0, depth):
        frame = frame.f_back
    output = "now"
    for _ in range(3):
        clsv = ""

        if "self" in frame.f_locals:
            instance = frame.f_locals["self"]
            if hasattr(instance, "__class__"):
                clsv = instance.__class__.__name__ + "."

        filename = os.path.basename(frame.f_code.co_filename)
        # print(frame.f_code.co_filename)
        output = f"{output}->[[{filename}].{clsv}{frame.f_code.co_name}]\n"
        if frame.f_back is not None:
            frame = frame.f_back
        else:
            break
    return output
