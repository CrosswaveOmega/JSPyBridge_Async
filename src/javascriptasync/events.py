import asyncio
import time, threading, json, sys
from typing import Any, Callable, Dict, List, Tuple
from . import config, pyi
from queue import Queue
from weakref import WeakValueDictionary

from .pyi import DUMMYI
from .logging import logs, log_print

from .connection import ConnectionClass
class TaskState:
    def __init__(self):
        self.stopping = False
        self.sleep = self.wait

    def wait(self, sec):
        stopTime = time.time() + sec
        while time.time() < stopTime and not self.stopping:
            time.sleep(0.2)
        if self.stopping:
            sys.exit(1)


class EventExecutorThread(threading.Thread):
    running = True
    jobs = Queue()
    doing = []

    def __init__(self):
        super().__init__(daemon=True)
        #self.daemon=True

    def add_job(self, request_id, cb_id, job, args):
        if request_id in self.doing:
            return  # We already are doing this
        self.doing.append(request_id)
        self.jobs.put([request_id, cb_id, job, args])

    def run(self):
        while self.running:
            request_id, cb_id, job, args = self.jobs.get()
            logs.debug('EVT %s, %s,%s,%s',request_id,cb_id,job,args)
            ok = job(args)
            if self.jobs.empty():
                self.doing = []


# The event loop here is shared across all threads. All of the IO between the
# JS and Python happens through this event loop. Because of Python's "Global Interperter Lock"
# only one thread can run Python at a time, so no race conditions to worry about.
class EventLoop:
    active = True
    queue = Queue()
    freeable = []

    callbackExecutor = EventExecutorThread()

    # This contains a map of active callbacks that we're tracking.
    # As it's a WeakRef dict, we can add stuff here without blocking GC.
    # Once this list is empty (and a CB has been GC'ed) we can exit.
    # Looks like someone else had the same idea :)
    # https://stackoverflow.com/questions/21826700/using-python-weakset-to-enable-a-callback-functionality
    callbacks = WeakValueDictionary()

    # The threads created managed by this event loop.
    threads = []

    outbound = []

    # After a socket request is made, it's ID is pushed to self.requests. Then, after a response
    # is recieved it's removed from requests and put into responses, where it should be deleted
    # by the consumer.
    requests = {}  # Map of requestID -> threading.Lock
    responses = {}  # Map of requestID -> response payload

    def __init__(self,config_container,amode=False):
        self.conn= ConnectionClass(config_container)
        self.conf=config_container
        if not amode:
            self.conn.start()
            self.callbackExecutor.start()
        self.pyi:pyi.PyInterface = pyi.PyInterface(config_container,self, None)


    # async def add_loop(self):
    #     loop=asyncio.get_event_loop()
    #     self.conn.set_conn(loop)
        
        #self.callbackExecutor.start()
    def stop(self):
        self.conn.stop()

    # === THREADING ===
    def newTaskThread(self, handler, *args):
        state = TaskState()
        t = threading.Thread(target=handler, args=(state, *args), daemon=True)
        self.threads.append([state, handler, t])
        logs.debug(
            "EventLoop: adding Task Thread. state=%s. handler=%s, args=%s",
                    str(state),
                    str(handler),
                    args)

        return t

    def startThread(self, method):
        for state, handler, thread in self.threads:
            if method == handler:
                thread.start()
                return
        t = self.newTaskThread(method)
        t.start()

    # Signal to the thread that it should stop. No forcing.
    def stopThread(self, method):
        for state, handler, thread in self.threads:
            if method == handler:
                logs.debug(
                    "EventLoop: stopping thread with handler %s",
                    str(method))
                state.stopping = True

    # Force the thread to stop -- if it doesn't kill after a set amount of time.
    def abortThread(self, method, killAfter=0.5):
        for state, handler, thread in self.threads:
            if handler == method:
                state.stopping = True
                killTime = time.time() + killAfter
                logs.debug(
                    "EventLoop: aborting thread with handler %s, kill time %f",
                    str(method),(killAfter))
                while thread.is_alive():
                    time.sleep(0.2)
                    if time.time() < killTime:
                        thread.terminate()

        self.threads = [x for x in self.threads if x[1] != method]

    # Stop the thread immediately
    def terminateThread(self, method):
        for state, handler, thread in self.threads:
            if handler == method:
                logs.debug(
                    "EventLoop: terminate thread with handler %s",
                    str(method))
                thread.terminate()
        self.threads = [x for x in self.threads if x[1] != method]

    # == IO ==

    # `queue_request` pushes this event onto the Payload
    def queue_request(self, request_id, payload, timeout=None)->threading.Event:
        self.outbound.append(payload)
        lock = threading.Event()
        self.requests[request_id] = [lock, timeout]
        logs.debug("EventLoop: queue_request. rid %s. payload=%s,  lock=%s, timeout:%s",str(request_id),str(payload),str(lock),timeout)
        self.queue.put("send")
        return lock

    def queue_payload(self, payload):
        self.outbound.append(payload)
        logs.debug("EventLoop: added %s to payload",str(payload))
        self.queue.put("send")

    def await_response(self, request_id, timeout=None)->threading.Event:
        lock = threading.Event()
        self.requests[request_id] = [lock, timeout]
        logs.debug("EventLoop: await_response. rid %s.  lock=%s, timeout:%s",str(request_id),str(lock),timeout)
        self.queue.put("send")
        return lock

    def on_exit(self):
        log_print('calling self.exit')
        log_print(str(self.responses))
        log_print(str(self.requests))
        log_print(str(self.pyi))
        if len(self.callbacks):
            logs.debug("%s,%s","cannot exit because active callback", self.callbacks)
        while len(self.callbacks) and self.conn.is_alive():
            time.sleep(0.4)
        time.sleep(0.8)  # Allow final IO
        self.callbackExecutor.running = False
        self.queue.put("exit")

    # === LOOP ===
    def loop(self):
        r=0
        while self.active:
            # Wait until we have jobs
            # if self.queue.empty():
            #     log_print('not empty')
            #     time.sleep(0.4)
            #     continue
            job=self.queue.get(block=True)

            #logs.debug("Loop: Queue get got %s",qu)
            # Empty the jobs & start running stuff !
            # NOTE: self.queue.empty doesn't empty queue's, it just checks if the queue
            # is empty.
            #self.queue.empty() - 

            # Send the next outbound request batch
            self.conn.writeAll(self.outbound)
            
            self.outbound = []

            # Iterate over the open threads and check if any have been killed, if so
            # remove them from self.threads
            #logs.debug("Loop: checking self.threads %s",",".join([str(s) for s in self.threads]))
            self.threads = [x for x in self.threads if x[2].is_alive()]
            
            if len(self.freeable) > 40:
                #
                self.queue_payload({"r": r, "action": "free", "ffid": "", "args": self.freeable})
                self.freeable = [] 

            # Read the inbound data and route it to correct handler
            inbounds = self.conn.readAll()
            for inbound in inbounds:
                logs.debug("Loop: inbounds was %s",str(inbound))
                r = inbound["r"]
                cbid = inbound["cb"] if "cb" in inbound else None
                if "c" in inbound and inbound["c"] == "pyi":
                    
                    logs.debug("Loop, inbound C request was %s",str(inbound))
                    j = inbound
                    self.callbackExecutor.add_job(r, cbid, self.pyi.inbound, inbound)
                if r in self.requests:
                    lock, timeout = self.requests[r]
                    barrier = threading.Barrier(2, timeout=5)
                    self.responses[r] = inbound, barrier
                    del self.requests[r]
                    lock.set()  # release, allow calling thread to resume
                    barrier.wait()