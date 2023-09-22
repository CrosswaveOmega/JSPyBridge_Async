
Threads and Tasks
=================

The base library provided some wrappers around threads. You aren't forced to use them, but they
help you avoid boilerplate and are simple to use.

*The only difference is you access the start, stop, and abort methods through the ThreadUtils static class.*

**This section is still a work in progress.  Names are not finalized.**


AsyncTask and Threads control
-----------------------------

.. code-block:: python
    :caption: general example.

    from javascriptasync import init_js, AsyncTask, ThreadUtils
    init_js()
    start,stop,abort=get_start_stop_abort()
    @AsyncTask(start=True)
    def routine(task: TaskState):
    ...

    # The signatures for the above functions :
    def ThreadUtils.start(fn: Function): ...
    def ThreadUtils.stop(fn: Function): ...
    def ThreadUtils.abort(fn: Function, killAfterSeconds: Optional[Int]): ...
    class TaskState:
        sleeping: bool
        def wait(seconds: Int): ...
        sleep = wait # Sleep is an alias to wait.


The "AsyncTask" decorator (no, it's not related to asyncio tasks) is a wrapper for creating background task threads.
Any (non ``async``) function you wrap with it will result in the creation of a thread, 
bound to the specified function. It will *not* automatically start the thread, unless the `start` parameter is set to True. 

Despite the name, it does not utilize the ``asyncio`` library.  It's for running synchronous methods in 
an almost "psuedo async" manner.  There is a equivalent wrapper for actual Asyncio Tasks after this section.

The first parameter to all "AsyncTask" methods should be a `TaskState` object:

.. autoclass:: javascriptasync.events.TaskState
   :members:
   :undoc-members:
   :no-index:
   

You can utilize the `ThreadUtils.start()`, `ThreadUtils.stop()` and `ThreadUtils.abort()` functions to control 
"AsyncTask" threads.

.. autoclass:: javascriptasync.ThreadUtils
   :members:
   :undoc-members:
   :no-index:

.. code-block:: python
    :caption: AsyncTask example

    import time
    from javascriptasync import init_js, AsyncTask, ThreadUtils
    init_js()
    @AsyncTask(start=False)
    def routine(task: TaskState):
    while not task.stopping: # You can also just do `while True` as long as you use task.sleep and not time.sleep
        ... do some repeated task ...
        task.sleep(1) # Sleep for a bit to not block everything else

    ThreadUtils.start(routine)
    time.sleep(1)
    ThreadUtils.stop(routine)


Actual Asyncio Task wrapping and control
========================================

Unlike ``"AsyncTask"``, this section actually uses asyncrounous methods as python defines them.

You don't really need the provided wrappers when dealing with asyncio Tasks, 
but it may help avoid boilerplate code like with the thread wrappers above.  

However, unlike the above, when an `asyncio.Task()` is created is always **started immediately.**  
The `AsyncTaskA` decorator is only to set an internal `is_async_task` attribute to the created coroutine.

For the sake of parity with the above, the first element should be a `TaskStateAsync` object:

.. autoclass:: javascriptasync.asynciotasks.TaskStateAsync
   :members:
   :undoc-members:
   :no-index:
   

Controlling asyncio tasks though this libary is done through the `AsyncTaskUtils` static class, in the same manner as the thread wrappers.

.. autoclass:: javascriptasync.AsyncTaskUtils
   :members:
   :undoc-members:
   :no-index:


* Transform async functions into Asyncio Tasks and start them using  `AsyncTaskUtils.start()`
* Stop the operation of Asyncio Tasks passed into `AsyncTaskUtils.start()` using `AsyncTaskUtils.stop()`
* Abort Asyncio Task operation using `AsyncTaskUtils.abort()`

The internal `TaskStateAsync` object is identical to `TaskState`, but uses `asyncio.sleep()` instead of `time.sleep()`.

.. code-block:: python
    :caption: AsyncTask example

    from javascriptasync import init_js, AsyncTaskA,AsyncTaskUtils 
    init_js()
    async def main():
        @AsyncTaskA()
            async def routine(task: TaskStateAsync):
            while not task.stopping: # You can also just do `while True` as long as you use task.sleep and not time.sleep
            ... do some repeated task ...
            await task.sleep(1) # This is a coroutine, remember to include await!  Sleep for a bit to not block everything else
        await AsyncTaskUtils.start(routine)
        await asyncio.sleep(5)
        await AsyncTaskUtils.stop(routine)
    asyncio.run(main())

