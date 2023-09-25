Wrapping Events and EventEmitters
=================================




Brief Overview of NodeJS's EventEmitter
---------------------------------------

Node.js's event-driven API is built upon 
objects called `EventEmitters <https://nodejs.org/api/events.html#events>`_
which *emits* and and *listens* for named events. 

EventEmitters allow you to assign listener functions that trigger whenever that event is triggered/emitted.

All Node.JS objects that emit events are instances of the EventEmitter class.

For the case of this library, there are four key methods of `EventEmitters <https://nodejs.org/api/events.html#events>`_ 
that should be noted.

:nodejs:`EventEmitter.on(eventName, listener)<#emitteroneventname-listener>`: 

    This method is used to register a listener function
    to be invoked whenever the specified `eventName` is emitted.
    Multiple listeners can be registered for the same event. 

    .. code-block:: javascript

        myEmitter.on('event', () => {
        console.log('an event occurred!');
        });


:nodejs:`EventEmitter.off(eventName, listener)<#emitteroffeventname-listener>`: 

    This method is an alias for `removeListener()`.
    It is used to remove a previously registered listener for the specified `eventName`. 

    .. code-block:: javascript

        myEmitter.off('event', listener);


:nodejs:`EventEmitter.once(eventName, listener)<#emitteroncefeventname-listener>`:

    This method is used to register a listener function 
    that will be called at most once for the specified `eventName`.
    After the event is emitted and the listener is invoked, it is automatically unregistered. 

    .. code-block:: javascript

        myEmitter.once('event', () => {
        console.log('this will only happen once');
        });

:nodejs:`EventEmitter.emit(eventName[, ...args])<##emitteremiteventname-args>`: 

    This method is used to trigger the emission of the specified `eventName`. 
    It invokes all registered listeners for that event synchronously in the order 
    in which they were registered. 
    Any additional arguments provided are passed to the listener functions.


    .. code-block:: javascript

        myEmitter.emit('event', arg1, arg2);


Utilizing EventEmitters From Python
-----------------------------------

To interact with EventEmitter on the python side, this library
primarily utilized a special set of functions that allow for the assignment of 
python functions as listeners for NodeJS EventEmitters, found within ``javascriptasync.emitters``.

.. automodule:: javascriptasync.emitters
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

These wrappers originally had to be used over the built-in `.on`, `.off` and `.once` 
methods of NodeJS's EventEmitters. 

...or at least, in the earlier versions.

Now, javascriptasync automatically wraps up EventEmitters into it's own type of proxy,
called the `EventEmitterProxy`.  It handles all the extra logic on it's own. 
EventEmitterProxy
^^^^^^^^^^^^^^^^^
.. autoclass:: javascriptasync.proxy.EventEmitterProxy
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:


Basic Usage Example
^^^^^^^^^^^^^^^^^^^

You can still use the `@On()` and  `@Once` decorators to assign listeners, but it's no longer needed.
There's also nothing stopping you from using the original wrappers.


.. code-block:: javascript
    :caption: emitter.js
    
    const EventEmitter = require('events');

    // Create a custom event emitter class
    class MyEmitter extends EventEmitter {
        constructor() {
            super();
            this.counter = 0;
        }

        // Method to increment and emit the "increment" event
        inc() {
            this.counter++;
            this.emit('increment', this.counter);
        }
    }

    // Export the custom emitter class
    module.exports = MyEmitter;



.. code-block:: python
    :caption: eventemitter.py

    from javascriptasync import init_js, require
    from javascriptasync.emitters import On, Once, off, once
    init_js()
    MyEmitter = require('./emitter.js')
    # New class instance
    myEmitter = MyEmitter()
    # Decorator usage
    @On(myEmitter, 'increment')
    def handleIncrement(this, counter):
        print("Incremented", counter)
        # Stop listening. `this` is the this variable in JS.
        off(myEmitter, 'increment', handleIncrement)
    # Trigger the event handler
    myEmitter.inc()

Async/Coroutine Event Handling
------------------------------

It's even possible to use `@On` and `@Once` on coroutine handler functions.

However, you will have to specify what asyncio event loop the coroutine will run in, 
you can either use `init_async`, or `set_async_loop` as of this update.


.. code-block:: python
    :caption: Async EventEmitter Example

    from javascriptasync import init_js, require_a, set_async_loop
    from javascriptasync.emitters import On, Once, off, once

    import asyncio

    async def main():
        await set_async_loop()
        MyEmitter = await require_a('./emitter.js')
        # New class instance
        myEmitter = MyEmitter()
        # Decorator usage
        
        @On(myEmitter, 'increment')#ASYNCLOOP MUST BE SET TO THE CURRENT EVENT LOOP, OR ELSE IT WILL CRASH.
        async def handleIncrement(this, counter):
            print("Incremented", counter)
            # Stop listening. `this` is the this variable in JS.
            await myEmitter.off_a('increment', handleIncrement)
        # Trigger the event handler
        myEmitter.inc()

    asyncio.run(main())
