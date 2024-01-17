import asyncio, time, sys
from typing import Coroutine, List, Tuple
from .core.abc import ThreadTaskStateBase
from .core.jslogging import logs


class TaskStateAsync(ThreadTaskStateBase):
    """
    Represents the state of a asyncio task.

    Attributes:
        stopping (bool): Indicates whether the task should stop.
        sleep (function): A function used to sleep for a specified duration.
    """

    def __init__(self):
        self.stopping = False
        # self.sleep = self.wait

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
            pass
            # print('STOP IN WAIT!')
            # sys.exit(1)

    async def sleep(self, sec):
        return await self.wait(sec)


class TaskGroup:
    """
    Handles creation, checks, and modifications to asyncio tasks.

    Attributes:
        state (TaskStateAsync): invoked method to initializes values of TaskStateAsync class.
        handler (Coroutine): handler to an asyncio task.
        task (asyncio.Task): the asyncio task created with the eventloop.
    """

    def __init__(self, handler: Coroutine, *args):
        """
        Initialize TaskGroup class.

        Args:
            handler (Coroutine): An asyncio Coroutine.
            *args: Variable length argument list.
        """
        self.state: TaskStateAsync = TaskStateAsync()
        self.handler: Coroutine = handler
        logs.debug(
            "EventLoop: adding Task. state=%s. handler=%s, args=%s",
            str(self.state),
            str(handler),
            args,
        )

        self.task: asyncio.Task = asyncio.create_task(handler(self.state, *args))

    def check_handler(self, handler: Coroutine) -> bool:
        """
        Checks if the handler method passed matches the existing one.

        Args:
            handler (Coroutine): An asyncio Coroutine to check.

        Returns:
            bool: True if the handler matches the existing one, False otherwise.
        """
        if self.handler == handler:
            return True
        return False

    async def stop_task(self):
        """
        Sets the stopping state of an asyncio task to True.
        """
        self.state.stop()

    async def abort_task(self, kill_after: float):
        """
        Stops an asyncio task and checks if task is complete till specified time duration.

        Args:
           kill_after (float): Time duration in seconds to check for task completion.
        """
        await self.stop_task()
        killTime = time.time() + kill_after
        logs.debug(
            "EventLoop: aborting task with handler %s, kill time %f",
            str(self.handler),
            (kill_after),
        )
        while not self.task.done():
            await asyncio.sleep(0.2)
            if time.time() > killTime:
                self.task.cancel()

    async def terminate_task(self):
        """
        Cancels the asyncio task object.
        """
        logs.debug("EventLoop: terminate task with handler %s", str(self.handler))
        self.task.cancel()

    def is_task_done(self):
        """check if the asyncio task is done."""
        return self.task.done()


class EventLoopMixin:
    """
    A mixin for EventLoop which defines additional functions for managing asyncio tasks.
    """

    tasks = []

    # === ASYNCIO ===
    async def newTask(self, handler: Coroutine, *args):
        """
        Create a new asyncio task.

        Args:
            handler(Coroutine): The async handler function for the task.
            *args: Additional arguments for the handler function.

        Returns:
            asyncio.Task: The created task.
        """
        newtask = TaskGroup(handler, *args)
        self.tasks.append(newtask)

        return newtask

    async def startTask(self, method: Coroutine):
        """
        Start an asyncio task.

        Args:
            method(Coroutine): The async method associated with the task.
        """
        for thr in self.tasks:
            if thr.check_handler(method):
                return

        await self.newTask(method)
        # asyncio.create_task(await task)
        # await task

    async def stopTask(self, method: Coroutine):
        """
        Stop an asyncio task.

        Args:
            method(Coroutine): The async method associated with the task.
        """
        for thr in self.tasks:
            if thr.check_handler(method):
                logs.debug("EventLoop: stopping task with handler %s", str(method))
                await thr.stop_task()

    async def abortTask(self, method: Coroutine, killAfter: float = 0.5):
        """
        Abort an asyncio task.

        Args:
            method(Coroutine): The async method associated with the task.
            killAfter (float): Time in seconds to wait before forcefully killing the task.
        """
        to_iterate = [x for x in self.tasks if x.check_handler(method)]
        for thr in to_iterate:
            await thr.abort_task(killAfter)

        self.tasks = [x for x in self.tasks if not x.check_handler(method)]

    async def terminateTask(self, method):
        """
        Terminate an asyncio task.

        Args:
            method: The async method associated with the task.
        """

        to_iterate = [x for x in self.tasks if x.check_handler(method)]
        for thr in to_iterate:
            await thr.terminate_task()

        self.tasks = [x for x in self.tasks if not x.check_handler(method)]
