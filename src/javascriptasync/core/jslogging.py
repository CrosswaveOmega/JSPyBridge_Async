import inspect
import logging
import os

"""
a simple logger.
"""

logs = logging.getLogger("asyncjs")
logs.setLevel(logging.WARNING)

# Create a console handler and set the level to Debug
console_handler = logging.StreamHandler()
# console_handler = logging.FileHandler("asyncjs.log")
# console_handler.setLevel(logs.getLevel())

# Create a formatter and add it to the console handler
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", dt_fmt)
console_handler.setFormatter(formatter)

# Add the console handler to the logs
logs.addHandler(console_handler)


def log_critical(msg, *args, **kwargs):
    if logs is not None:
        logs.critical(msg, *args, **kwargs)


def log_error(msg, *args, **kwargs):
    if logs is not None:
        logs.error(msg, *args, **kwargs)


def log_info(msg, *args, **kwargs):
    if logs is not None:
        logs.info(msg, *args, **kwargs)


def log_warning(msg, *args, **kwargs):
    if logs is not None:
        logs.warning(msg, *args, **kwargs)


def log_debug(msg, *args, **kwargs):
    if logs is not None:
        logs.debug(msg, *args, **kwargs)


def log_print(*msg):
    logs.info(str(msg))


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
