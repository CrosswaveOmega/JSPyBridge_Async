/* eslint-disable new-cap */
/**
 * The Python Interface for JavaScript
 */
const pyObjs=require('./PyObject');

// const util = require('util');

if (typeof performance === 'undefined') {
  // eslint-disable-next-line no-var
  var {performance} = require('perf_hooks');
}
const log = () => { };
const errors = require('./errors');
// use REQ_TIMEOUT env var value if parseable as integer,
// otherwise default to 100000 (ms)
const REQ_TIMEOUT = parseInt(process.env.REQ_TIMEOUT) || 100000;
/**
 * Custom exception for errors that occur in the Bridge.
 *
 * @class
 * @extends Error
 */
class BridgeException extends Error {
  /**
   * Creates a new instance of BridgeException.
   * @param {...any} a - Additional parameters for
   *  the base Error class.
   */
  constructor(...a) {
    super(...a);
    this.message += ` Python didn't respond in time (${
      REQ_TIMEOUT
    }ms), look above for any Python errors. If no errors, the API call hung.`;
    // We'll fix the stack trace once this is shipped.
  }
}


/**
 * Custom exception for Python-related errors.
 *
 * @class
 * @extends Error
 */
class PythonException extends Error {
  /**
   * Creates a new instance of PythonException.
   * @param {string[]} stack - The call stack.
   * @param {Error} error - The Python error object.
   */
  constructor(stack, error) {
    super();
    const failedCall = stack.join('.');
    const trace = this.stack.split('\n').slice(1).join('\n');

    // Stack is generated at runtime when (and if) the error is printed
    Object.defineProperty(this, 'stack', {
      get: () => errors.getErrorMessage(
          failedCall, trace, error || this.pytrace),
    });
  }
  /**
   * Sets the Python trace for the exception.
   * @param {string} value - The Python trace to set.
   */
  setPythonTrace(value) {
    // When the exception is thrown, we don't want
    // this to be printed out.
    // We could also use new class "hard-privates"
    Object.defineProperty(this, 'pytrace', {enumerable: false, value});
  }
}
/**
 * Asynchronously waits for a callback to resolve within a specified timeout.
 *
 * @function
 * @async
 * @param {function} cb - The callback function to wait for.
 * @param {number} withTimeout - The timeout duration in milliseconds.
 * @param {function} onTimeout - The callback to execute when
 * the timeout occurs.
 * @return {Promise<any>} - A promise resolving to the
 * result of the callback or 'timeout'.
 */
async function waitFor(cb, withTimeout, onTimeout) {
  let t;
  if (withTimeout === Infinity) return new Promise((resolve) => cb(resolve));
  const ret = await Promise.race([
    new Promise((resolve) => cb(resolve)),
    new Promise((resolve) => {
      t = setTimeout(() => resolve('timeout'), withTimeout);
    }),
  ]);
  clearTimeout(t);
  if (ret === 'timeout') onTimeout();
  return ret;
}
/**
 * An enumeration representing different modes for
 * generating unique snowflake integers
 * @enum {number}
 */
const SnowflakeMode = {
  // A unique "mode" Enum for generating a unique snowflake
  // based on the desired request.
  pyrid: 0,
  jsffid: 1,
  jsrid: 2,
  pyffid: 3,
};
/**
 * Generates a unique snowflake value based on the
 * current timestamp and a specified mode.
 *
 * @function
 * @param {number} parameter - An integer from 0 to 131071.
 * @param {SnowflakeMode} [mode=SnowflakeMode.jsrid] -
 * The 'mode' for what the generated snowflake is for.
 * @return {number} - The generated snowflake value.
 */
function generateSnowflake(parameter, mode = SnowflakeMode.jsrid) {
  // Validate that parameter is within the
  // 0-131071 (0x1FFFF) range, use a modulo if it isn't.
  // I have to do this BigInt conversion for each
  // because the bitshift operator in JavaScript
  // automatically converts operands into 32 bits,
  // resulting in data loss!
  let param=BigInt(parameter);
  if (!(param >= 0 && param <= BigInt('0x1FFFF'))) {
    param=param% BigInt(0x20000);
  }

  const timestamp = BigInt(Math.floor(Date.now()/1000)) & BigInt('0xFFFFFFFF');
  // console.log('timestamp', timestamp, (timestamp << BigInt(20)));
  const snowflake = ((timestamp << BigInt(20))) | (
    (BigInt(mode) & BigInt('0x07')) << BigInt(17)) | (param & BigInt('0x1FFFF')
  );
  // console.log('Now snowflake is ', snowflake);
  return parseInt(snowflake.toString(), 10);
}

let nextReqId = 10000;
// function nextReq(){  return generateSnowflake(nextReqId++)}
const nextReq = () => generateSnowflake(nextReqId++);

/**
 * Python Bridge instance for communication
 *  between JavaScript and Python.
 *
 * Properties:
 * {IPCClass} com - an interprocess communication object.
 * {Object} jrefs - a ref map used so Python can call back JS APIs.
 * {Bridge} jsi - The main JavaScript Bridge object.
 * {Array} freeable - stores items that can be garbage collected.
 * {Function} loop - creates intervals to manage tasks.
 * {FinalizationRegistry} finalizer - Registry for managing garbage collection.
 *
 * @class
 */
class PyBridge {
  /**
   * Creates a new instance of PyBridge.
   *
   * @constructor
   * @param {IPCClass} com - an interprocess communication object.
   * @param {Bridge} jsi - The main JavaScript Bridge object.
   */
  constructor(com, jsi) {
    this.com = com;
    // This is a ref map used so Python can call back JS APIs
    this.jrefs = {};
    this.jsi = jsi;

    // We don't want to GC things individually, so batch all the GCs at once
    // to Python
    this.freeable = [];
    this.loop = setInterval(this.runTasks, 1000);

    // This is called on GC
    this.finalizer = new FinalizationRegistry((ffid) => {
      this.freeable.push(ffid);
      // Once the Proxy is freed, we also want to release the pyClass ref
      delete this.jsi.m[ffid];
    });
    globalThis.JSPyBridge = {

      python: this.makePyObject(0).python,
    };
  }
  /**
   * This method free a list of Python objects by sending the list of ids
   * to the Python instance and clears the freeable list.
   */
  runTasks = () => {
    if (this.freeable.length) this.free(this.freeable);
    this.freeable = [];
  };


  /**
   * Ends the PyBridge instance by clearing the interval loop.
   */
  end() {
    clearInterval(this.loop);
  }
  /**
   * Sends a request to Python with a callback.
   *
   * @param {object} req - The request object.
   * @param {function} cb - The callback function.
   */
  request(req, cb) {
    // When we call Python functions with Proxy paramaters,
    // we need to just send the FFID
    // so it can be mapped on the python side.
    req.c = 'pyi';
    this.com.write(req, cb);
  }
  /**
   * Gets the length of an object in Python.
   *
   * @async
   * @param {number} ffid - The FFID of the Python object.
   * @param {string[]} stack - The call stack.
   * @return {Promise<number>} - A promise resolving to the length
   * of the Python object.
   */
  async len(ffid, stack) {
    const req = {
      r: nextReq(),
      action: 'length',
      ffid: ffid,
      key: stack,
      val: '',
    };
    const resp = await waitFor(
        (cb) => this.request(req, cb), REQ_TIMEOUT, () => {
          throw new BridgeException(
              `Attempt to access '${stack.join('.')}' failed.`,
          );
        });
    if (resp.key === 'error') throw new PythonException(stack, resp.sig);
    return resp.val;
  }
  /**
   * Gets a value from a Python object.
   *
   * @async
   * @param {number} ffid - The FFID of the Python object.
   * @param {string[]} stack - The call stack.
   * @param {any[]} args - The arguments for the Python call.
   * @param {boolean} [suppressErrors=false] - Flag to suppress errors.
   * @return {Promise<any>} - A promise
   * resolving to the value from the Python object.
   */
  async get(ffid, stack, args, suppressErrors) {
    const req = {
      r: nextReq(),
      action: 'get',
      ffid: ffid,
      key: stack,
      val: args};

    const resp = await waitFor(
        (cb) => this.request(req, cb),
        REQ_TIMEOUT, () => {
          throw new BridgeException(
              `Attempt to access '${stack.join('.')}' failed.`,
          );
        });
    if (resp.key === 'error') {
      if (suppressErrors) return undefined;
      throw new PythonException(stack, resp.sig);
    }
    switch (resp.key) {
      case 'string':
      case 'int':
        return resp.val; // Primitives don't need wrapping
      default: {
        const py = this.makePyObject(resp.val, resp.sig);
        this.queueForCollection(resp.val, py);
        return py;
      }
    }
  }

  // This does a function call to Python.
  // We assign the FFIDs, so we can assign them and send the call to Python.
  // We also need to keep track of the Python objects so we can GC them.
  /**
   * Calls a Python function.
   *
   * @async
   * @param {number} ffid - The FFID of the Python object.
   * @param {string[]} stack - The call stack.
   * @param {any[]} args - The arguments for the Python call.
   * @param {object} kwargs - The keyword arguments for the Python call.
   * @param {boolean} set - Flag indicating if it's a set operation.
   * @param {number} [timeout] - The timeout duration for the call.
   * @return {Promise<any>} - A promise resolving
   * to the result of the Python call.
   */
  async call(ffid, stack, args, kwargs, set, timeout) {
    const r = nextReq();
    // console.log('callffid',ffid, stack, args, kwargs, set, timeout)
    const req = {
      r,
      c: 'pyi',
      action: set ? 'setval' : 'pcall',
      ffid: ffid,
      key: stack,
      val: [args, kwargs]};
    const payload = JSON.stringify(req, (k, v) => {
      if (!k) return v;
      if (v && !v.r) {
        if (v.ffid) return {ffid: v.ffid};
        if (
          typeof v === 'function' ||
          (typeof v === 'object' && (
            v.constructor.name !== 'Object' && v.constructor.name !== 'Array'
          )
          )
        ) {
          // console.log(this.jsi.ffid);
          const ffid = this.jsi.ffidinc();
          // console.log(ffid);
          this.jsi.m[ffid] = v;
          this.queueForCollection(ffid, v);
          return {ffid};
        }
      }
      return v;
    });

    const stacktrace = new PythonException(stack);
    const resp = await waitFor(
        (resolve) => this.com.writeRaw(payload, r, resolve),
        timeout || REQ_TIMEOUT, () => {
          throw new BridgeException(
              `Attempt to access '${stack.join('.')}' failed.`,
          );
        });
    if (resp.key === 'error') {
      stacktrace.setPythonTrace(resp.sig);
      throw stacktrace;
    }

    if (set) {
      return true; // Do not allocate new FFID if setting
    }

    log('call', ffid, stack, args, resp);
    switch (resp.key) {
      case 'string':
      case 'int':
        return resp.val; // Primitives don't need wrapping
      default: {
        const py = this.makePyObject(resp.val, resp.sig);
        this.queueForCollection(resp.val, py);
        return py;
      }
    }
  }
  /**
   * Gets the value of a Python object.
   *
   * @async
   * @param {number} ffid - The FFID of the Python object.
   * @param {string[]} stack - The call stack.
   * @return {Promise<any>} - A promise resolving
   * to the value of the Python object.
   */
  async value(ffid, stack) {
    const req = {r: nextReq(),
      action: 'value',
      ffid: ffid,
      key: stack,
      val: ''};
    const resp = await waitFor(
        (cb) => this.request(req, cb),
        REQ_TIMEOUT, () => {
          throw new BridgeException(
              `Attempt to access '${stack.join('.')}' failed.`,
          );
        });
    if (resp.key === 'error') throw new PythonException(stack, resp.sig);
    return resp.val;
  }
  /**
   * Inspects a Python object.
   *
   * @async
   * @param {number} ffid - The FFID of the Python object.
   * @param {string[]} stack - The call stack.
   * @return {Promise<any>} -
   * A promise resolving to the inspection result of the Python object.
   */
  async inspect(ffid, stack) {
    const req = {
      r: nextReq(),
      action: 'inspect',
      ffid: ffid,
      key: stack,
      val: '',
    };
    const resp = await waitFor(
        (cb) => this.request(req, cb),
        REQ_TIMEOUT, () => {
          throw new BridgeException(
              `Attempt to access '${stack.join('.')}' failed.`,
          );
        });
    if (resp.key === 'error') throw new PythonException(stack, resp.sig);
    return resp.val;
  }
  /**
   * Frees Python objects with the specified FFIDs.
   *
   * @async
   * @param {number[]} ffids - The FFIDs of the Python objects to free.
   * @return {Promise<boolean>} - A promise resolving to true if successful.
   */
  async free(ffids) {
    const req = {r: nextReq(), action: 'free', ffid: '', key: '', val: ffids};
    this.request(req);
    return true;
  }
  /**
   * Queues a Python object for collection by registering it with the finalizer.
   *
   * @function
   * @param {number} ffid - The FFID of the Python object.
   * @param {any} val - The Python object value.
   */
  queueForCollection(ffid, val) {
    this.finalizer.register(val, ffid);
  }
  /**
   * Creates a Python object Proxy with a custom handler
   * for chaining and logging.
   *
   * @function
   * @param {number} ffid - The FFID of the Python object.
   * @param {string} inspectString - The string used for inspecting
   * the Python object.
   * @return {Proxy} - A Proxy representing the Python object
   * with a custom handler.
   */
  makePyObject(ffid, inspectString) {
    const pyobj=new pyObjs.PyObject(ffid, inspectString, this);

    return new Proxy(new pyObjs.CustomLogger(inspectString), pyobj);
  }
}

module.exports = {PyBridge, SnowflakeMode, generateSnowflake};
