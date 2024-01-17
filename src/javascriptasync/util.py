# importing importlib.util module
import enum
import importlib.util


import time
from typing import Union


MAX_SAFE_INTEGER = 0xFFFFFFFFFFFFF


def haspackage(name: str):
    """
    Checks if a Python library exists.

    Args:
        name (str): The name of the Python library to check.

    Returns:
        bool: True if the library exists, False otherwise.
    """
    # code to check if the library exists
    if (spec := importlib.util.find_spec(name)) is not None:
        return True
    # else displaying that the module is absent
    else:
        return False


class SnowflakeMode(enum.Enum):
    """A unique "mode" Enum for generating a unique snowflake based on the desired request."""

    pyrid = 0
    jsffid = 1
    jsrid = 2
    pyffid = 3


def generate_snowflake(
    parameter: int, mode: Union[int, SnowflakeMode] = SnowflakeMode.pyrid
) -> int:
    """
    Generates a unique snowflake value based on the current timestamp
    and a passed in 'mode' parameter.

    Args:
        parameter(int): integer from 0-131071.
        mode(Union[int,SnowflakeMode]): Determines which type of snowflake to generate.
        The python side of the bridge only uses SnowflakeMode.pyrid and SnowflakeMode.pyffid


    """
    r = mode
    param = parameter
    # Validate that parameter is within the 0-131071 (0x1FFFF) range, use a modulo if it isn't.
    if not (0 <= param <= 0x1FFFF):
        param = param % 0x20000
        # raise ValueError("Parameter value must be in the range [0, 131071]")
    if isinstance(mode, SnowflakeMode):
        r = int(mode.value)
    else:
        r = mode
    timestamp = int(time.time())  # Get the current time in SECONDS.
    snowflake = ((timestamp & 0xFFFFFFFF) << 20) | ((int(r) & 0x7) << 17) | (param & 0x1FFFF)

    # This has to be no more than 52 bits.
    if snowflake >= (2**52 - 1):
        print("WARNING: A generated snowflake value seems to be too big for JavaScript!")
        # Otherwise, warn and shorten it.
        snowflake = snowflake & MAX_SAFE_INTEGER
    return snowflake
