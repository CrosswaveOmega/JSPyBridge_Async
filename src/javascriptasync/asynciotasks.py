import asyncio, time, sys

from .logging import logs
class TaskStateAsync:
    """
    Represents the state of a asyncio task.

    Attributes:
        stopping (bool): Indicates whether the task should stop.
        sleep (function): A function used to sleep for a specified duration.
    """
    def __init__(self):
        self.stopping = False
        self.sleep = self.wait

    async def wait(self, sec):
        """
        Wait for a specified duration.

        Args:
            sec (float): The duration to wait in seconds.
        """
        stopTime = time.time() + sec
        while time.time() < stopTime and not self.stopping:
            await asyncio.sleep(0.2)
        if self.stopping:
            print('STOP IN WAIT!')
            #sys.exit(1)

class EventLoopMixin:
    '''
    A mixin for EventLoop which defines additional functions for managing asyncio tasks.
    '''
    tasks=[]
    def __init__(self):
        self.tasks = []

    # === ASYNCIO ===
    async def newTask(self, handler, *args):
        """
        Create a new asyncio task.

        Args:
            handler: The async handler function for the task.
            *args: Additional arguments for the handler function.

        Returns:
            asyncio.Task: The created task.
        """
        state = TaskStateAsync()
        print('asynciotype',handler,type(handler))
        task = asyncio.create_task(handler(state, *args))
        self.tasks.append([state, handler, task])
        logs.debug(
            "EventLoop: adding Task. state=%s. handler=%s, args=%s",
            str(state),
            str(handler),
            args)

        return task

    async def startTask(self, method):
        """
        Start an asyncio task.

        Args:
            method: The async method associated with the task.
        """
        for state, handler, task in self.tasks:
            if method == handler:
                return

        task = await self.newTask(method)
        #asyncio.create_task(await task)
        #await task

    async def stopTask(self, method):
        """
        Stop an asyncio task.

        Args:
            method: The async method associated with the task.
        """
        for state, handler, task in self.tasks:
            if method == handler:
                logs.debug(
                    "EventLoop: stopping task with handler %s",
                    str(method))
                state.stopping = True

    async def abortTask(self, method, killAfter=0.5):
        """
        Abort an asyncio task.

        Args:
            method: The async method associated with the task.
            killAfter (float): Time in seconds to wait before forcefully killing the task.
        """
        for state, handler, task in self.tasks:
            if handler == method:
                state.stopping = True
                killTime = time.time() + killAfter
                logs.debug(
                    "EventLoop: aborting task with handler %s, kill time %f",
                    str(method), (killAfter))
                while not task.done():
                    await asyncio.sleep(0.2)
                    if time.time() > killTime:
                        task.cancel()

        self.tasks = [x for x in self.tasks if x[1] != method]

    async def terminateTask(self, method):
        """
        Terminate an asyncio task.

        Args:
            method: The async method associated with the task.
        """
        for state, handler, task in self.tasks:
            if handler == method:
                logs.debug(
                    "EventLoop: terminate task with handler %s",
                    str(method))
                task.cancel()

        self.tasks = [x for x in self.tasks if x[1] != method]