# JSPyBridge_async - javascript asyncio fork
[![PyPI](https://img.shields.io/pypi/v/javascriptasync)](https://pypi.org/project/javascriptasync/)
[![Build Status](https://github.com/CrosswaveOmega/JSPyBridge_Async/workflows/Node.js%20CI/badge.svg)](https://github.com/extremeheat/JSPyBridge/actions/workflows/)



Interoperate Node.js from Python, with asyncio compatibility. **Work in progress.** 

This is a fork of [JSPyBridge](https://github.com/extremeheat/JSPyBridge) by extremeheat, created to properly integrate `asyncio` events and coroutines into the python side of the bridge.


As the purpose of this fork was only to alter the `javascript` package, it's specifically for running Node.js from Python.  No changes are made to `pythonia` or are planned to be made to `pythonia`.
### current stable install
```
 pip install -U javascriptasync
```
### current latest installation
```
 pip install -U git+https://github.com/CrosswaveOmega/JSPyBridge_Async.git
```


Requires Node.js 14 and Python 3.8 or newer.

## Key Features

* Ability to call async and sync functions and get object properties with a native feel
* Built-in garbage collection
* Bidirectional callbacks with arbitrary arguments
* Iteration and exception handling support
* Object inspection allows you to easily `console.log` or `print()` any foreign objects

* (Bridge to call JS from Python) Native decorator-based event emitter support
* (Bridge to call JS from Python) **First-class Jupyter Notebook/Google Colab support.** See some Google Colab uses below.

## KEY CHANGES:
* `javascript` is now `javascriptasync`
* `config.py` has been encapsulated into the `JSConfig` class, all objects that need to access variables within `JSConfig` have been passed an object reference to a single unique `JSConfig` instance.
 * `__init__.py` utilizes a singleton to ensure that only one instance of an JSConfig class is created at any one time.  You need to call `init()` to start up the bridge!
* debug output now uses the logging module.
* `connection.py` has been encapsulated into the `ConnectionClass`, accessable through the `events.EventLoop` class, as `events.EventLoop` is the only place the connection was ever utilized.
* It's possible to set a custom timeout value when using eval_js.
* async variants of `require` and `eval_js` are included within __init__.py, as `require_a` and `eval_js_a` respectively.
* this package is now built using a `pyproject.toml` file instead of a `setup.py` script.
* `test_general.py` now works with pytest.
* `console`, `globalThis`, and `RegExp` have to be retrieved with the `get_console()`, `get_globalThis()`, and `get_RegExp()` functions.
* `start`, `stop`, and `abort` has to be retrieved with through the `ThreadUtils` static class.
* any call or init operation can be made into a coroutine by passing in the `coroutine=True` keyword.
* Separate set of wrappers for asyncio tasks through `AsyncTaskUtils` 
* Event Emitters can utilize Coroutine handlers.
### New Javascript from Python usage:
```py
import asyncio
from javascriptasync import init_js, require_a, get_globalThis
init_js()
async def main():
  chalk, fs = await require_a("chalk")
  globalThis=get_globalThis()
  datestr=await (await globalThis.Date(coroutine=True)).toLocaleString(coroutine=True)
  print("Hello", chalk.red("world!"), "it's", datestr)
  fs.writeFileSync("HelloWorld.txt", "hi!")

asyncio.run(main)
```
## TO DO:
 * better documentation and examples
 * bug fixing/optimization.
 * callback an asyncio coroutine from JavaScript
 * Code cleanup.


## Basic usage example

See some examples [here](https://github.com/CrosswaveOmega/JSPyBridge_Async/tree/master/examples). See [documentation](https://github.com/CrosswaveOmega/JSPyBridge_Async#documentation) below and in [here](https://github.com/CrosswaveOmega/JSPyBridge_Async/tree/master/docs).



### Examples
 see https://github.com/CrosswaveOmega/JSPyBridge_Async/tree/master/examples



# Documentation

## From Python
The bridge has to be initalized before use, this can be done via the `init_js()` function
```py
from javascriptasync import init_js
init_js()
```
You can import the bridge module with 
```py
from javascriptasync import require
```

This will import the require function which you can use just like in Node.js. This is a slightly
modified require function which does dependency management for you. The first paramater is the name
or location of the file to import. Internally, this calls the ES6 dynamic `import()` function. Which
supports both CommonJS and ES6 modules.

If you are passing a module name (does not start with / or include a .) such as 'chalk', it will search 
for the dependency in the internal node_module folder and if not found, install it automatically. 
This install will only happen once, it won't impact startup afterwards.

The second paramater to the built-in require function is the version of the package you want, for
example `require('chalk', '^3')` to get a version greater than major version 3. Just like you would
if you were using `npm install`. It's reccomended to only use the major version as the name and version
will be internally treated as a unique package, for example 'chalk--^3'. If you leave this empty, 
we will install `latest` version instead, or use the version that may already be installed globally.

If require is being used within an asyncio coroutine, you should be using `require_a()` instead to prevent blocking your asyncio event loop.
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

### Usage

* All function calls to JavaScript are thread synchronous **by default.**
  * This can be changed by including a `coroutine=True` kwarg in a function call on a Proxy.
  * Currently, only function `calls` and `inits` can be coroutines for the sake of simplicity.
* ES6 classes can be constructed without new
* ES5 classes can be constructed with the .new psuedo method
* Use `@On` decorator when binding event listeners. Use `off` to disable it.
  * You can bind a coroutine as an event listener, provided you pass in a reference to your running asyncio event loop.
* All callbacks run on a dedicated callback thread. DO NOT BLOCK in a callback or all other events will be blocked. Instead:
* ~~Use the @AsyncTask decorator when you need to spawn a new thread for an async JS task.~~
* The @AsyncTask decorator is only for syncronous functions that you wish to run in a psuedo asyncronous(i.e, not with asyncio) way.  For Coroutines, wrappers are provided to quickly create Tasks which run on your event loop.

For more, see [docs/python.md](https://github.com/CrosswaveOmega/JSPyBridge_Async/tree/master/docs/python.md).

### Usage

<details>
  <summary>👉 Click here to see some code usage examples 👈</summary>

### Basic import

Let's say we have a file in JS like this called `time.js` ...
```js
function whatTimeIsIt() {
    return (new Date()).toLocaleString()
}
module.exports = { whatTimeIsIt }
```

Then we can call it from Python !
```py
from javascript import require
time = require('./time.js')
print(time.whatTimeIsIt())
```

### Event emitter

*You must use the provided On, Once, decorator and off function over the normal dot methods.*

emitter.js
```js
const { EventEmitter } = require('events')
class MyEmitter extends EventEmitter {
    counter = 0
    inc() {
        this.emit('increment', ++this.counter)
    }
}
module.exports = { MyEmitter }
```

listener.py
```py
from javascript import require, On, off
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

### ES5 class

es5.js
```js
function MyClass(num) {
    this.getNum = () => num
}
module.exports = { MyClass }
```


es5.py
```py
MyEmitter = require('./es5.js')
myClass = MyClass.new(3)
print(myClass.getNum())
```

### Iteration
items.js
```js
module.exports = { items: [5, 6, 7, 8] }
```

items.py
```py
items = require('./items.js')
for item in items:
    print(item)
```

### Callback

callback.js
```js
export function method(cb, salt) {
    cb(42 + salt)
}
```
callback.py
```py
method = require('./callback').method
# Example with a lambda, but you can also pass a function ref
method(lambda v: print(v), 2) # Prints 44
```

</details>

## From JavaScript

* All the Python APIs are async. You must await them all. 
* Use `python.exit()` or `process.exit()` at the end to quit the Python process.
* This library doesn't manage the packaging. 
  * Right now you need to install all the deps from pip globally, but later on we may allow loading from pip-envs.
* When you do a normal Python function call, you can supply "positional" arguments, which must 
  be in the correct order to what the Python function expects.
* Some Python objects accept arbitrary keyword arguments. You can call these functions by using
  the special `$` function syntax. 
  * When you do a function call with a `$` before the parenthesis, such as `await some.pythonCall$()`, 
    the final argument is evaluated as a kwarg dictionary. You can supply named arguments this way.
* Property access with a $ at the end acts as a error suppression operator. 
  * Any errors will be ignored and instead undefined will be returned
* See [docs/javascript.md](docs/javascript.md) for more docs, and the examples for more info

### Usage

<details>
  <summary>👉 Click here to see some code usage examples 👈</summary>

### Basic import

Let's say we have a file in Python like this called `time.py` ...
```py
import datetime
def what_time_is_it():
  return str(datetime.datetime.now())
```

Then we can call it from JavaScript !
```js
import { python } from 'pythonia'
const time = await python('./time.py')
console.log("It's", await time.what_time_is_it())
python.exit()
```

### Iterating

* When iterating a Python object, you *must* use a `for await` loop instead of a normal `for-of` loop.

iter.py
```py
import os
def get_files():
  for f in os.listdir():
    yield f
```

iter.js
```js
const iter = await python('./iter.py')
const files = await iter.get_files()
for await (const file of files) {
  console.log(file)
}
```
</details>

## Details
* When doing a function call, any foreign objects will be sent to you as a reference. For example,
  if you're in JavaScript and do a function call to Python that returns an array, you won't get a
  JS array back, but you will get a reference to the Python array. You can still access the array
  normally with the [] notation, as long as you use await. If you would like the bridge to turn
  the foreign refrence to something native, you can request a primitive value by calling `.valueOf()`
  on the Python array. This would give you a JS array. It works the same the other way around.
* The above behavior makes it very fast to pipe data from one function onto another, avoiding costly
  conversions.
* This above behavior is not present for callbacks and function parameters. The bridge will try to
  serialize what it can, and will give you a foreign reference if it's unable to serialize something.
  So if you pass a JS object, you'll get a Python dict, but if the dict contains something like a class,
  you'll get a reference in its place.

#### Notable details

* The `ffid` keyword is reserved. You cannot use it in variable names, object keys or values as this is used to internlly track objects.
* On the bridge to call JavaScript from Python, due to the limiatations of Python and cross-platform IPC, we currently communicate over standard error which means that JSON output in JS standard error can interfere with the bridge. The same issue exists on Windows with python. You are however very unlikely to have issues with this.

* You can set the Node.js/Python binary paths by setting the `NODE_BIN` or `PYTHON_BIN` enviornment variables before importing the library. Otherwise, the `node` and `python3` or `python` binaries will be called relative to your PATH enviornment variable. 

* Function calls will timeout after 100000 ms and throw a `BridgeException` error. That default value can be overridden by defining the new value of `REQ_TIMEOUT` in an environment variable.