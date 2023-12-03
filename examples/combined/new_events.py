from javascriptasync import init_js, require

init_js()
MyEmitter = require('./emitter.js')
# New class instance
myEmitter = MyEmitter()
# define callback function.
def handleIncrement(this, counter):
    print("Incremented", counter)
    # Stop listening. `this` is the this variable in JS.
    myEmitter.off( 'increment', handleIncrement)

myEmitter.on('increment',handleIncrement)
# Trigger the event handler
myEmitter.inc()