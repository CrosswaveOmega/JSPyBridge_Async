class ThreadTaskStateBase:
    """Base class for the "ThreadState" and "TaskStateAsync" """

    def __init__(self):
        self.stopping = False
        self.sleep = self.wait

    def wait(self, sec):
        raise Exception("NOT DEFINED.")


class BaseError(Exception):
    """Base error class."""


class EventLoopBase:
    """Base Class for the Event Loop"""
