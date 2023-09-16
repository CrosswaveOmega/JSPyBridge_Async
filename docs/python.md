# Docs for bridge to call JavaSript from Python

(See README.md for some additional details)

It's functionally equivalent to the original `javascript` library, with the major front end differences being the manual bridge initalization,asyncio compatible require and eval_js methods, and optionally asyncronous JavaScript init, and function calls. 
* All function calls to JavaScript are thread synchronous by default.
  * This can be changed by including a `coroutine=True` kwarg in the function call
* ES6 classes can be constructed without new
* ES5 classes can be constructed with the .new psuedo method
* Use `@On` decorator when binding event listeners. Use `off` to disable it.
* You can bind a coroutine as an event listener, provided you pass in a reference to your running asyncio event loop.
* All callbacks run on a dedicated callback thread. DO NOT BLOCK in a callback or all other events will be blocked. Instead:
* Use the @AsyncTask decorator when you need to spawn a new thread for an async JS task.
## Proxy Init And Call.
 This fork allows you to utilice a reserved 'coroutine' argument whenever initalizing or calling a method on the JS side of the bridge.  This allows your asyncio event loop to continue with other task while waiting on the node.js side of the bridge.

```py
import asyncio
from javascriptasync import init_js, require_a
init_js()
async def main():
  chalk= await require_a("chalk")
  red=await chalk.red("world!",coroutine=True)
  print("Hello", red)

asyncio.run(main)
```


## Built-ins

Dependencies are automatically manged through the library through the `require` function. If
you run into issues with dependencies, you can clear the internal `node_modules` folder cache
by using `python3 -m javascriptasync --clean` in a command line.

You can update the internal packages with `python3 -m javascriptasync --update <npm package>`. 

You can install a package internally by using `python3 -m javascriptasync --install <npm package>`. Internally, whatever you place after --update will be passed to `npm install <...>`. For example, use `python3 -m javascriptasync --install PrismarineJS/vec3` to install the `vec3` package from git.

### imports

```py
def require ( package_name: str, package_version: Optional[str] = None ) -> Void
```

* `package_name` : The name of the npm package you want to import. If you use a relative import
  (starting with . or /) then it will load the file relative to where your calling script is.
* `package_version` : The version of the npm package you want to install. If blank, first try to
  require from the local or global npm registry. If not found, install the specified package name
  and version. These two combine to create a unique ID, for example `chalk--1.0`. This ensures two
  different versions don't collide. This parameter is ignored for relative imports.

There is also an asyncronous variant of require.
```py
async def require_a ( package_name: str, package_version: Optional[str] = None ) -> Void
```
 Use this if you don't want to block an active asyncio event loop.  Remember to utilize `await`!
* `package_name` : The name of the npm package you want to import. If you use a relative import
  (starting with . or /) then it will load the file relative to where your calling script is.
* `package_version` : The version of the npm package you want to install. If blank, first try to
  require from the local or global npm registry. If not found, install the specified package name
  and version. These two combine to create a unique ID, for example `chalk--1.0`. This ensures two
  different versions don't collide. This parameter is ignored for relative imports.

### threads

The base library provided some wrappers around threads. You aren't forced to use them, but they
help you avoid boilerplate and are simple to use.

**The only difference is you access the start, stop, and abort methods through the ThreadUtils static class.**

```py
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
```

The AsyncTask decorator is a wrapper for creating threads. Any function you wrap with it will
result in the creation of a thread, bound to the specified function. It will *not* automatically
start the thread, unless `start` parameter is set to True. 

The `ThreadUtils.start()`, `ThreadUtils.stop()` and `ThreadUtils.abort()` functions all relate to AsyncTask threads. If you didn't
already start a AsyncTask, you can programmatically start it later with `ThreadUtils.start(routine)`. If you
want a thread to stop, you can send a `stopping` signal to it. The first parameter to all AsyncTaskUtils
is a `TaskState` object. That object has a `stopping` variable, and a `wait` function. The stopping
variable indicates that the thread should exit immediately, and it's your responsibility to make
sure it does. The `wait` function that exists in TaskState will sleep, but also automatically exit 
the process once the `stopping` flag is True. 

```py
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
```

If you need to be 100% sure the thread has stopped, you can use `abort(fn, seconds)` function instead. This
will kill the thread if it doesn't kill in n seconds. It's not good pratice to kill Python threads, so
avoid this when possible. To avoid trouble, `stop()` does not force the thread to exit, it just asks.

### Asyncio Task support.

You don't really need the provided wrappers when dealing with asyncio Tasks, but it may help avoid boilerplate code like with the thread wrappers above.  With asyncio, when a task is created it's **started immediately.**  The `AsyncTaskA` decorator is only to set the internal `is_async_task` attribute to the created coroutine.

Operating asyncio tasks though this libary is done through the `AsyncTaskUtils` static class, in the same manner as the thread wrappers.

* Transform async functions into Asyncio Tasks and start them using  `AsyncTaskUtils.start()`
* Stop the operation of Asyncio Tasks passed into `AsyncTaskUtils.start()` using `AsyncTaskUtils.stop()`
* Abort Asyncio Task operation using `AsyncTaskUtils.abort()`

The internal `TaskStateAsync` object is identical to `TaskState`, but uses `asyncio.sleep()` instead of `time.sleep()`.
```py
import time
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
```
### events

This library provides some wrappers around EventEmitters. You must use them over the built-in
`.on`, `.off` and `.once` methods of normal EventEmitters. You can still use `.emit` normally.

These wrappers are avaliable as `@On(emitter, eventName)`, `@Once(emitter, eventName)` and
the top-level `off(emitter, eventName, handlerFn)` function.

Note that you are still able to use the `once` static function from Node.js's `emitter` library.
This library provides a default export for this, used as in the example below.

```py
from javascriptasync import init_js, require, On, Once, off, once
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
```

### async event handlers.

It is possible to use `@On` and `@Once` on coroutine handler functions.  

**However, you will have to pass in an active asyncio event loop into the decorator as an argument!**


```py
from javascriptasync import init_js, require, On, Once, off, once
init_js()
import asyncio

async def main():
  MyEmitter = require('./emitter.js')
  # New class instance
  myEmitter = MyEmitter()
  # Decorator usage
  asyncloop=asyncio.get_event_loop()
  
  @On(myEmitter, 'increment',asyncloop)#ASYNCLOOP MUST BE SET TO THE CURRENT EVENT LOOP, OR ELSE IT WILL CRASH.
  async def handleIncrement(this, counter):
      print("Incremented", counter)
      # Stop listening. `this` is the this variable in JS.
      off(myEmitter, 'increment', handleIncrement)
  # Trigger the event handler
  myEmitter.inc()

asyncio.run(main())
```

### expression evaluation

You can use the exported `eval_js` function to evaluate JavaScript code within the current Python context. The parameter to this function is a JS string to evaluate, with access to all the Python variables in scope. Inside the JavaScript code block, Make sure to use `await` anywhere you do a function call or a property access on a Python object. You can set variables without await.

**Unique to this fork, you can set a timeout value on the python side.**

```julia
import javascriptasync
javascriptasync.init_js()
countUntil = 9
myArray = [1]
myObject = { 'hello': '' }

# Make sure you await everywhere you expect a JS call !
output = javascript.eval_js('''
    myObject['world'] = 'hello'    
    for (let x = 0; x < countUntil; x++) {
        await myArray.append(2)
    }
    return 'it worked'
''', timeout=20)

# If we look at myArray and myObject, we should see it updated
print(output, myArray, myObject)
```
There's also an asyncrounous variant in eval_js_a

```julia
import javascriptasync
javascriptasync.init_js()
countUntil = 9
myArray = [1]
myObject = { 'hello': '' }

# Make sure you await everywhere you expect a JS call !
output = await javascript.eval_js_a('''
    myObject['world'] = 'hello'    
    for (let x = 0; x < countUntil; x++) {
        await myArray.append(2)
    }
    return 'it worked'
''', timeout=20)

# If we look at myArray and myObject, we should see it updated
print(output, myArray, myObject)
```

You can also use it inline.
```swift
x_or_z = eval_js(''' obj.x ?? obj.z ''')
```