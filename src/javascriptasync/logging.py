import logging
import os
'''
a simple logger.
'''
logs = logging.getLogger('asyncjs')
logs.setLevel(logging.DEBUG)

# Create a console handler and set the level to Debug
#console_handler=logging.StreamHandler()
console_handler = logging.FileHandler('asyncjs.log')
console_handler.setLevel(logs.level)

# Create a formatter and add it to the console handler
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',dt_fmt)
console_handler.setFormatter(formatter)

# Add the console handler to the logs
logs.addHandler(console_handler)
def log_print(*msg):
    logs.info(str(msg))


def set_log_level(level):
    logs.setLevel(level)
    console_handler.setLevel(logs.level)

def print_path(frame):
    output='now'
    for _ in range(5):
        clsv=""
        if "self" in frame.f_locals:
            instance = frame.f_locals["self"]
            if hasattr(instance, "__class__"):
                clsv = instance.__class__.__name__+"."
        filename = os.path.basename(frame.f_code.co_filename)
        output=f'{output}->[[{filename}].{clsv}{frame.f_code.co_name}]'
        if frame.f_back is not None:
            frame = frame.f_back
        else:
            break
    return output
    