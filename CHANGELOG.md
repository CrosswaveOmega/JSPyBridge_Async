# 0.2.0.1
* Documentation touchups, and accounting for latest change in parent package.

# 0.2.0.0
* the getattr/setattr/and call magicmethods in Proxy now have proper asyncronous variants, along with the async proxy chaining system.
* The magic methods in Proxy now just refer to non magic variants for the sake of better control over Calls back and fourth across the bridge.
* The EventEmitter frontend methods have been moved to it's own emitters.py file.
* NodeJS's EventEmitters now create a separate child class of Proxy called EventEmitterProxy with built in methods that wrap around the on, off, and once methods.  This is because using the standalone on, off, and once wrapper functions for an object methods felt like an overcomplication.
* Proxy now has asyncronous iterators.
* The read method in PYI has been commented out, since there is no 'apiin' anymore.
* PYI can now use async functions as callbacks, provided PYI was passed a reference to an active asyncio event loop. 

# 0.1.1.0
* ConnectionClass now checks if NodeJS was installed before startup
* Fixed docstrings where FFID was "Function ID" and not "Foreign Object Reference ID"



## 0.1.0.1
* Added sphinx documentation for library.
* Added custom exception types.
* Cleaned up misc objects.

## 0.1.0

* Initial release of javascriptasync.
* Fixed numerous typos found in source files.
* Refactored library into a more Object Oriented structure
  - config.py refactored into a specialized JSConfig class, since the library initalizes everything in there at runtime.
  -  Config singleton introduced to ensure only one JSConfig is initalized by front end methods.
  - connection.py refactored into a single ConnectionClass, initalized at runtime as a member of EventLoop
  - all objects which required config.py attributes now include a reference to JSConfig.
* Frontend methods (in init.py) utilize the Config singleton to access the active JSConfig object.  Now throw an exception whenever they're used without initalizing JSConfig.
* Executor now has a async variant to pcall, using a special CrossThreadEvent decendant of asyncio.Event
* Separate Mixin for initalizing asyncio tasks in the same way as the "AsyncTask" decorator.
* Applied docstrings to the frontend methods.
* Began applying proper typing and documentation for the rest of the package.