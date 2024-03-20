"""
Core module which contains the EventLoop class.

"""


from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio
import random
import time, threading
from typing import Any, Callable, Dict, List, Tuple, Union

from queue import Queue, Empty
from weakref import WeakValueDictionary

from .errorsjs import NodeTerminated
from .core.abc import Request, EventObject

from .core.jslogging import (
    log_critical,
    log_debug,
    log_error,
    log_info,
    log_warning,
)

from .connection import ConnectionClass
from .util import generate_snowflake
from .asynciotasks import EventLoopMixin, TaskGroup

from .threadtasks import ThreadGroup, ThreadManagerMixin

if TYPE_CHECKING:
    from .configjs import JSConfig


PayloadType = Union[str, Dict, Request]

EVENT_EMITTER_CALLBACK_MAX_HOLDUP = 20


class CrossThreadEvent(asyncio.Event, EventObject):
    """
    Initalize Asyncio Event and pass in a specific
    Asyncio event loop, and ensure that the event can be
    Set outside an asyncio event loop."""

    __slots__ = ["_superloop", "output", "timeout_happened", "event_lock"]

    def __init__(self, *args, _loop=None, **kwargs):
        self._superloop = None

        super().__init__(*args, **kwargs)
        if self._superloop is None:
            self._superloop = _loop
        self.output = None
        self.timeout_happened = False
        self.event_lock = threading.Lock()

    def set(self):
        self._superloop.call_soon_threadsafe(super().set)

    def clear(self):
        self._superloop.call_soon_threadsafe(super().clear)

    async def wait(self):
        self._superloop = asyncio.get_event_loop()
        await super().wait()


class CrossThreadEventSync(threading.Event, EventObject):
    """
    Threading.Event equivalent to CrossThreadEvent.
    For use in syncronous mode."""

    __slots__ = ["output", "timeout_happened", "event_lock"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout_happened = False
        self.output = None
        self.event_lock = threading.Lock()


class EventExecutorThread(threading.Thread):
    """Represents a thread for executing Pythonside Callbacks.

    Attributes:
        running (bool): Indicates whether the thread is running.
        jobs (Queue[Tuple(str,str,Callable,Tuple[Any, ...])]): A queue for storing jobs to be executed.
        doing (list): A list of jobs currently being executed.
    """

    def __init__(self):
        self.doing: List[Any] = []
        self.running: bool = True
        self.jobs: Queue[Tuple(str, str, Callable, Tuple[Any, ...])] = Queue()
        super().__init__(daemon=True)
        # self.daemon=True

    def add_job(self, request_id, cb_id, job, args):
        """
        Add a job to the event executor thread.

        Args:
            request_id: The ID of the request.
            cb_id: The ID of the callback.
            job: The job function to execute.
            args: Arguments for the job.
        """
        if request_id in self.doing:
            return  # We already are doing this
        self.doing.append(request_id)
        self.jobs.put([request_id, cb_id, job, args])

    def run(self):
        """
        Run the event executor thread.
        """
        while self.running:
            request_id, cb_id, job, args = self.jobs.get()
            log_debug("EVT %s, %s,%s,%s", request_id, cb_id, job, args)
            ok = job(args)
            if ok:
                log_debug("EVT %s, %s,%s,%s,%s", request_id, cb_id, job, args, ok)
            if self.jobs.empty():
                self.doing = []


# The event loop here is shared across all threads. All of the IO between the
# JS and Python happens through this event loop. Because of Python's "Global Interperter Lock"
# only one thread can run Python at a time, so no race conditions to worry about.
class EventLoop(EventLoopMixin, ThreadManagerMixin):
    """
    A shared syncronous event loop which manages all IO between Python and Node.JS.

    Attributes:
        active (bool): Indicates whether the event loop is active.
        queue (Queue): A queue for storing events to be processed.  When a job is added to the queue, the loop continues.
        freeable (list): A list of freeable items.
        callbackExecutor (EventExecutorThread): An event executor thread for handling callbacks.
        callbacks (WeakValueDictionary): A dictionary of active callbacks that are being tracked.
        threads (list): A list of threads managed by the event loop.
        outbound (Queue): A list of outbound payloads.
        requests (dict): A dictionary of request IDs and locks.
        responses (dict): A dictionary of response data and barriers.
        conn(ConnectionClass): Instance of the connection class.
        config(JSConfig): The JSConfig instance this class belongs to.

    """

    __slots__ = [
        "active",
        "queue",
        "freeable",
        "upper_batch_limit",
        "callbackExecutor",
        "callbacks",
        "threads",
        "tasks",
        "outbound",
        "requests",
        "responses",
        "config",
        "conn",
    ]

    def __init__(self, config_container: JSConfig):
        """
        Initialize the EventLoop.

        This EventLoop coordinates all communication between the Python side of the bridge and the
        NodeJS side of the bridge.

        Args:
            config_container (JSConfig): Reference to the active JSConfig object
        """
        self.active: bool = True
        self.queue = Queue()
        self.freeable = []
        self.upper_batch_limit = 20

        self.callbackExecutor = EventExecutorThread()

        # This contains a map of active callbacks that we're tracking.
        # As it's a WeakRef dict, we can add stuff here without blocking GC.
        # Once this list is empty (and a CB has been GC'ed) we can exit.
        # Looks like someone else had the same idea :)
        # https://stackoverflow.com/questions/21826700/using-python-weakset-to-enable-a-callback-functionality
        self.callbacks = WeakValueDictionary()

        # The threads created managed by this event loop.
        self.threads: List[ThreadGroup] = []
        self.tasks: List[TaskGroup] = []
        self.outbound: Queue[Dict[str, Any]] = Queue()

        # After a socket request is made, it's ID is pushed to self.requests. Then, after a response
        # is recieved it's removed from requests and put into responses, where it should be deleted
        # by the consumer.
        self.requests: Dict[int, EventObject] = {}
        # Map of requestID -> threading.Lock
        self.responses: Dict[int, Tuple[Dict, threading.Barrier]] = {}
        # Map of requestID -> response payload
        self.conn: ConnectionClass = ConnectionClass(config_container)
        self.config: JSConfig = config_container
        # if not amode:

    # async def add_loop(self):
    #     loop=asyncio.get_event_loop()
    #     self.conn.set_conn(loop)

    def start_connection(self):
        """
        Starts the callbacks handler thread for processing callbacks
        and the connection to Node.JS.
        """
        self.conn.start()
        self.callbackExecutor.start()

    def stop(self):
        """
        Stop the event loop.
        """
        self.conn.stop()

    # == IO ==
    def _add_request(self, request_id: int, event_object: EventObject, timeout=None):
        """Add a new request to the requests dictionary and send

        Args:
            request_id (int): The ID of the request.
            event_object (EventObject): The EventObject, either a
            timeout (float, optional): Unused. Defaults to None.
        """
        self.requests[request_id] = [event_object, timeout]
        log_debug(
            "EventLoop: queue_request. rid %s.  lock=%s, timeout:%s",
            str(request_id),
            str(event_object),
            timeout,
        )
        self.queue.put("send")

    # `queue_request` pushes this event onto the Payload
    def queue_request(
        self, request_id: int, payload: PayloadType, timeout=None
    ) -> Union[CrossThreadEventSync, CrossThreadEvent]:
        """
        Queue a request to be sent with the payload

        Args:
            request_id: The ID of the request.
            payload (PayloadType): The payload to be sent.
            timeout (float): Timeout duration in seconds.

        Returns:
            Union[CrossThreadEventSync]: A thread syncronous event for waiting on the response.
        """

        self.outbound.put(payload)
        lock = CrossThreadEventSync()
        self._add_request(request_id, lock, timeout)

        return lock

    # `queue_request` pushes this event onto the Payload
    async def queue_request_a(
        self, request_id: int, payload: PayloadType, timeout=None
    ) -> Union[CrossThreadEventSync, CrossThreadEvent]:
        """
        Queue a request to be sent with the payload

        Args:
            request_id: The ID of the request.
            payload: The payload to be sent.
            timeout (float): Timeout duration in seconds.

        Returns:
            Union[CrossThreadEventSync,CrossThreadEvent]: An event for waiting on the response.
        """

        self.outbound.put(payload)
        lock = CrossThreadEvent(_loop=asyncio.get_event_loop())

        self._add_request(request_id, lock, timeout)
        return lock

    def queue_payload(self, payload: PayloadType):
        """
        Add a payload to the outbound queue.
        Args:
            payload: The payload to be sent.
        """
        self.outbound.put(payload)
        log_debug("EventLoop: added %s to payload", str(payload))
        self.queue.put("send")

    def free_ffid(self, ffid: int):
        """
        Schedule a free operation for a JavaScript object on the other
        side of the bridge.

        Args:
            ffid (int): Foreign Object Reference ID of the object to be freed.
        """
        self.freeable.append(ffid)

    def await_response(self, request_id: int, timeout=None) -> CrossThreadEventSync:
        """
        Return a lock event for an expected responce given a request_id

        Args:
            request_id: The ID of the request.
            timeout (float): Timeout duration in seconds.  Unused.

        Returns:
            CrossThreadEventSync: An EventObject which will activate once the
            response_id is returned from NodeJS.
        """
        lock = CrossThreadEventSync()

        self._add_request(request_id, lock, timeout)
        return lock

    async def await_response_a(self, request_id: int, timeout=None) -> CrossThreadEvent:
        """
        Return a lock event for an expected responce given a request_id,
        for use when a Coroutine is going to handle the revent.

        Args:
            request_id: The ID of the request.
            timeout (float): Timeout duration in seconds.  Unused.

        Returns:
            CrossThreadEvent: An WAsyncio EventObject which will activate once the
            response_id is returned from NodeJS.
        """

        lock = CrossThreadEvent(_loop=asyncio.get_event_loop())

        self._add_request(request_id, lock, timeout)
        return lock

    def on_exit(self):
        """
        Handle the exit of the event loop.
        """
        log_info("calling self.on_exit")
        log_info("requests:[%s],responses:[%s]", str(self.requests), str(self.responses))
        log_info("callbacks: [%s]", str(",".join([f"{k,v}" for k, v in self.callbacks.items()])))
        if len(self.callbacks):
            log_debug("%s,%s", "cannot exit because active callback", self.callbacks)
        while len(self.callbacks) and self.conn.is_alive():
            callback_end_counter = 0
            while self.conn.is_alive() and callback_end_counter < EVENT_EMITTER_CALLBACK_MAX_HOLDUP:
                time.sleep(0.4)
                callback_end_counter += 1
            if len(self.callbacks) and self.conn.is_alive():
                log_error("couldn't exit because of callback...")
                choose = random.choice(list(self.callbacks.keys())) if self.callbacks else None
                if choose:
                    del self.callbacks[choose]

        time.sleep(0.8)  # Allow final IO
        # self.callbackExecutor.running = False
        log_info("Sending shutdown command.")
        self.queue_payload({"r": generate_snowflake(4092, 0), "action": "shutdown"})
        self.queue.put("exit")

        time.sleep(0.8)  # Allow final IO
        self.conn.stop()

    # def get_response_from_id(self, request_id: int) -> Tuple[Any, threading.Barrier]:
    #     """ DEPRECATED - Data is simply returned through the Event!
    #     Retrieve a response and associated barrier for a given request ID,
    #      and then removes it from the internal responces dictionary.

    #     Args:
    #         request_id (int): The request ID for which the response and barrier are needed.

    #     Returns:
    #         Tuple[Any, threading.Barrier]: A tuple containing the response and the
    #         threading.Barrier associated with the request.

    #     Raises:
    #         KeyError: If the specified request ID does not exist in the responses.

    #     """
    #     if not request_id in self.responses:
    #         raise KeyError(f"Response id {request_id} not in self.responses")
    #     res, barrier = self.responses[request_id]
    #     del self.responses[request_id]
    #     return res, barrier

    def _send_outbound(self):
        """
        Gather all jobs in the outbound Queue, and send to the active
        connection process.
        """
        out = []
        current_iter = 0
        still_full = True
        try:
            while self.outbound.qsize() > 0 and still_full:
                try:
                    toadd = self.outbound.get_nowait()
                    out.append(toadd)
                    current_iter += 1
                    if current_iter > self.upper_batch_limit:
                        self.conn.writeAll(out)
                        out, current_iter = [], 0
                except Empty as e:
                    log_warning("EventLoop, outbound Queue is empty.", exc_info=e)
                    still_full = False
            self.conn.writeAll(out)
        except NodeTerminated as e:
            log_critical("Attempted to write to a terminated process! %s", e)

    def _remove_finished_thread_tasks(self):
        """Remove all killed/finished threads and tasks from the
        threads and tasks lists."""
        log_debug("Loop: checking self.threads %s", ",".join([str(s) for s in self.threads]))
        self.threads = [x for x in self.threads if x.is_thread_alive()]
        log_debug("Loop: checking self.tasks %s", ",".join([str(s) for s in self.tasks]))
        self.tasks = [x for x in self.tasks if x.is_task_done() is False]

    def _free_if_above_limit(self, ra: int = 20, lim: int = 40):
        """
        Send a free request across the bridge if size of the
        freeable list was exceeded.

        Args:
            ra (int): Request ID to be assigned to request.
            lim (int, optional): How big freeable must be to activate. Defaults to 40.
        """
        r = generate_snowflake(ra % 131071)
        if len(self.freeable) > lim:
            self.queue_payload({"r": r, "action": "free", "ffid": "", "args": self.freeable})
            self.freeable = []

    def _fatal_error(self):
        """Called when notified of JS error."""
        errorst = self.conn.kill_error["error_severe"]
        allkeys = list(self.requests.keys())
        log_critical("JS killed by error: Terminating keys %s", allkeys)
        for r in allkeys:
            inbound = {"r": r, "key": "error", "error": errorst}
            self._publish_inbound(r, inbound)
        self.active = False
        self.config.throw_error_state(errorst)

    def _publish_inbound(self, r, inbound):
        """Publish inbound data to the relevant calling task."""
        event, timeout = self.requests.pop(r)
        event: EventObject = event
        # barrier = threading.Barrier(2, timeout=5)
        # The data is only going one way, back to the thread/coroutine
        # which made the request in the first place.
        # There's no reason to use a barrier.

        if not event.was_timeout():
            event.publish(inbound)

        else:
            log_warning("Request %d timed out: %s", r, timeout)

    def _recieve_inbound(self, oldr: int):
        """
        Read the inbound data from the connection, and route it
        to the correct handler.

        Args:
            oldr (int): Old request_id

        Returns:
            int: the latest recieved request id from outbound.
        """
        r = oldr
        # It's going to learn about the error here first.
        inbounds = self.conn.readAll()

        if self.conn.kill_error:
            log_critical("FATAL.")
            self._fatal_error()
            return r
        for inbound in inbounds:
            log_debug("Loop: inbounds was %s", str(inbound))
            r = inbound["r"]
            cbid = inbound["cb"] if "cb" in inbound else None
            if "c" in inbound and inbound["c"] == "pyi":
                log_debug("Loop, inbound C request was %s", str(inbound))

                mypyi = self.config.get_pyi()
                # syncio.create_task(asyncio.to_thread(pyi.inbound,inbound))
                self.callbackExecutor.add_job(r, cbid, mypyi.inbound, inbound)
            if r in self.requests:
                # Call the publish inbound sub method.
                self._publish_inbound(r, inbound)

        return r

    def process_job(self, job: str, r: int) -> int:
        """
        send/recieve all outbound/inbound messages to/from connection.

        First, the job will be logged for debugging purposes. Then, all outbound messages will be
        sent via the connection. After that, the function will check each thread to see if they are
        still alive, and remove any dead threads from the thread list.
        If the length of self.freeable exceeds 40,
        a payload to free the job is added to the queue.

        The last part of the process is reading the inbound data
        and routing it to the correct handler.
        This function ends by returning the request id.

        Args:
            job (str): A string representing the job to be processed.
            r (int): The id of the last request processed.

        Returns:
            int: The id of the processed request.
        """
        # log_debug("Loop: Queue get got %s",qu)
        # Empty the jobs & start running stuff !
        # NOTE: self.queue.empty does not empty queue,
        # it just checks if the queue is empty.
        # commented out.
        # self.queue.empty() -

        # Send the next outbound request batch

        log_debug(f"Running job {job}, {r}.  outbound={self.outbound.qsize()}")
        self._send_outbound()

        # remove finished tasks/threads
        self._remove_finished_thread_tasks()

        # Request free if freeable is above the given limit.
        self._free_if_above_limit(r)

        # Read the inbound data and route it to correct handler
        r = self._recieve_inbound(r)
        return r

    # === LOOP ===
    def loop(self):
        """
        Main loop for processing events and managing IO.
        """

        r = 0
        while self.active:
            # Wait until we have jobs
            # if self.queue.empty():
            #     log_print('not empty')
            #     time.sleep(0.4)
            #     continue

            job = self.queue.get(block=True)
            if job == "exit":
                self.active = False
                break
            r = self.process_job(job, r)
