# JSPyBridge_async - javascript asyncio fork
[![PyPI](https://img.shields.io/pypi/v/javascriptasync)](https://pypi.org/project/javascriptasync/)
[![Documentation Status](https://readthedocs.org/projects/asyncjavascriptbridge/badge/?version=latest)](https://asyncjavascriptbridge.readthedocs.io/?badge=latest)
[![Build Status](https://github.com/CrosswaveOmega/JSPyBridge_Async/workflows/Node.js%20CI/badge.svg)](https://github.com/extremeheat/JSPyBridge/actions/workflows/)



Interoperate Node.js from Python, with built in asyncio compatibility. 

This is a fork of [JSPyBridge](https://github.com/extremeheat/JSPyBridge) by extremeheat, created to properly integrate `asyncio` events and coroutines into the python side of the bridge.

As the purpose of this fork was only to alter the `javascript` package, it's specifically for running Node.js from Python.  No changes are made to `pythonia` or are planned to be made to `pythonia`.
### current stable installation
```
 pip install -U javascriptasync
```
### current latest installation
```
 pip install -U git+https://github.com/CrosswaveOmega/JSPyBridge_Async.git
```


Requires Node.js 14 and Python 3.8 or newer.

## Key Features
* use node.js objects in the same way as python modules.
* Ability to call async and sync functions and get object properties with a native feel
* Built-in garbage collection
* Bidirectional callbacks with arbitrary arguments
* Iteration and exception handling support
* Object inspection allows you to easily `console.log` or `print()` any foreign objects

* (Bridge to call JS from Python) Specialized object oriented support for event-emitter functions.
* retrieve blob objects from the Javascript side of the bridge.
* enhanced support for concurrent operations.

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
 * bug fixing/optimization
 * Code cleanup.


## KEY CHANGES:
* `javascript` is now `javascriptasync`
* `config.py` has been encapsulated into the `JSConfig` class, all objects that need to access variables within `JSConfig` have been passed an object reference to a single unique `JSConfig` instance.
 * `__init__.py` utilizes a singleton to ensure that only one instance of an JSConfig class is created at any one time.  You need to call `init()` to start up the bridge!
 * The `JSContext` object can be utilized to make use of the library's operations in a more object oriented manner.
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


### Examples
 see https://github.com/CrosswaveOmega/JSPyBridge_Async/tree/master/examples

