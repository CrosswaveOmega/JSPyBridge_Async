
// const util = require('util');
// const {inspect} = require('node:util');
const customInspectSymbol = Symbol.for('nodejs.util.inspect.custom');

/**
   * Intermediate" objects are returned while chaining.
   * If the user tries to log an Intermediate then we know
   * they forgot to use await, as if they were to use
   * await, then() would be implicitly called
   * where we wouldn't return a Proxy, but a Promise.
   * Must extend Function to be a "callable" object in JS for the Proxy.
   *
   * @class
   * @extends Function
   */
class Intermediate extends Function {
  /**
       * Creates a new instance of Intermediate.
       * @param {string[]} callstack - The call stack.
       */
  constructor(callstack) {
    super();
    this.callstack = [...callstack];
  }
  // eslint-disable-next-line valid-jsdoc
  /**
       * Custom inspect method to remind users to
       *  use await when calling a Python API.
       *
       * @function
       * @return {string} - The inspection message.
       */
  [customInspectSymbol](depth, inspectOptions, inspect) {
    return '\n[You must use await when calling a Python API]\n';
  }
}

/**
 * Represents a Python object, created by PyBridge.makePyObject();
 *
 * @class
 */
class PyObject {
  /**
   * @constructor
   *
   * @param {number} ffid - File Format ID.
   * @param {string} inspectString - The string returned by inspect.
   * @param {PyBridge} parentBridge - The parent bridge.
   */
  constructor(ffid, inspectString, parentBridge) {
    this.ffid = ffid;
    this.inspectString = inspectString;
    this.parentBridge = parentBridge;
  }
  /**
   * Custom get handler for the Proxy object.
   *
   * @param {Object} target - The object upon which to perform the operations.
   * @param {string|symbol} prop - The property or symbol that was referenced.
   * @param {Object} reciever - The object originally passed to the proxy.
   * @return {*} The value retrieved from the target object/tailored functions
   *    based on the prop value.
   */
  get=(target, prop, reciever) => {
    const next = new Intermediate(target.callstack);
    // log('```prop', next.callstack, prop)
    const ffid=this.ffid;

    if (prop === '$$') return target;
    if (prop === 'ffid') return this.ffid;
    if (prop === 'toJSON') return () => ({ffid});
    if (prop === 'toString' && this.inspectString) return target[prop];

    if (prop === 'then') {
      // Avoid .then loops
      if (!next.callstack.length) {
        return undefined;
      }
      return (resolve, reject) => {
        this.parentBridge.get(
            this.ffid, next.callstack, [],
        ).then(resolve).catch(reject);
        next.callstack = []; // Empty the callstack afer running fn
      };
    }

    if (prop === 'length') {
      return this.parentBridge.len(this.ffid, next.callstack, []);
    }

    if (typeof prop === 'symbol') {
      if (prop === Symbol.iterator) {
        // This is just for destructuring arrays
        return function* iter() {
          for (let i = 0; i < 100; i++) {
            const next = new Intermediate([...target.callstack, i]);
            yield new Proxy(next, handler);
          }
          throw new SyntaxError(
              'You must use `for await` when iterating over'+
                  'a Python object in a for-of loop',
          );
        };
      }

      if (prop === Symbol.asyncIterator) {
        const parentBridge=this.parentBridge;
        return async function* iter() {
          const it = await parentBridge.call(0, ['Iterate'], [{ffid}]);
          while (true) {
            // eslint-disable-next-line new-cap
            const val = await it.Next();
            if (val === '$$STOPITER') {
              return;
            } else {
              yield val;
            }
          }
        };
      }

      log('Get symbol', next.callstack, prop);
      return;
    }

    if (Number.isInteger(parseInt(prop))) {
      prop = parseInt(prop);
    }

    next.callstack.push(prop);
    // no $ and not fn call, continue chaining
    return new Proxy(next, this);
  };
  /**
   * Handles invocation for the function call.
   *
   * @this {PyObject}
   * @param {Object} target - Target object.
   * @param {Object} self - unused
   * @param {Array} args - List of arguments.
   * @return {*} Result of the function call or action on the callstack.
   */
  apply=(target, self, args) => {
    const ffid = this.ffid;
    const final = target.callstack[target.callstack.length - 1];
    let kwargs;
    let timeout;
    if (final === 'apply') {
      target.callstack.pop();
      args = [args[0], ...args[1]];
    } else if (final === 'call') {
      target.callstack.pop();
    } else if (final?.endsWith('$')) {
      kwargs = args.pop();
      timeout = kwargs.$timeout;
      delete kwargs.$timeout;
      target.callstack[target.callstack.length - 1] = final.slice(0, -1);
    } else if (final === 'valueOf') {
      target.callstack.pop();
      const ret = this.parentBridge.value(ffid, [...target.callstack]);
      return ret;
    } else if (final === 'toString') {
      target.callstack.pop();
      const ret = this.parentBridge.inspect(ffid, [...target.callstack]);
      return ret;
    }
    // console.log('ffid', ffid,
    //     'tc', target.callstack,
    //     'args', args,
    //     'kwargs', kwargs,
    //     'boo', false,
    //     'timeout', timeout);
    const ret = this.parentBridge.call(
        ffid,
        target.callstack,
        args,
        kwargs,
        false,
        timeout,
    );
    target.callstack = []; // Flush callstack to py
    return ret;
  };
  /**
   * Assign value to a described property on an existing target.
   *
   * @this {PyObject}
   * @param {Object} target - Target object.
   * @param {(string|symbol)} prop - Property or symbol to be set.
   * @param {*} val - Value to be set.
   * @return {*} - Result from parentBridge.call operation.
   */
  set=(target, prop, val) => {
    if (Number.isInteger(parseInt(prop))) prop = parseInt(prop);
    const ret = this.parentBridge.call(
        this.ffid,
        [...target.callstack],
        [prop, val],
        {},
        true);
    return ret;
  };
}
/**
       * Represents a custom logger function for
       * synchronously logging Python objects.
       *
       * @class
       * @extends Function
       */
class CustomLogger extends Function {
  /**
   * Constructs a new instance of CustomLogger.
   *
   * @param {string} inspectString - The string to inspect.
   */
  constructor(inspectString) {
    super();
    this.inspectString=inspectString;
    this.callstack = [];
  }
  // eslint-disable-next-line valid-jsdoc
  /**
       * Custom inspect method for logging Python objects.
       *
       * @function
       * @return {string} - The inspectString or a default message.
       */
  [customInspectSymbol](depth, inspectOptions, inspect) {
    return this.inspectString || '(Some Python object)';
  }
}
module.exports= {PyObject, Intermediate, CustomLogger};
