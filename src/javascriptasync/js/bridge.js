/* eslint-disable no-var */
/* eslint-disable camelcase */
if (
  typeof process !== 'undefined' &&
  parseInt(process.versions.node.split('.')[0]) < 14) {
  console.error('Your node version is currently', process.versions.node);
  console.error('Please update it to a version >= 14.x.x from https://nodejs.org/');
  process.exit(1);
}
/*
 * The JavaScript Interface for Python
 */
try {
  const util = require('util');
  const EventEmitter = require('events');
  // const fs = require('fs');
  const {PyBridge, SnowflakeMode, generateSnowflake} = require('./pyi');
  const {$require, AsyncQueue} = require('./deps');
  const {once} = require('events');

  const debug = process.env.DEBUG?.includes(
      'jspybridge',
  ) ? (...args) => console.debug(`[${args}]`) : () => { };
  const supportsColors = false;
  const autoInspect = true;
  /**
 * Determines the "type" of the provided object
 * according to a custom series of checks.
 *
 * @param {any} obj - The object that you would like to check the type of.
 *
 * @return {string} - A string representing the "type"
 *   of the object according to the following criteria:
 * - If the object has a 'ffid' property, returns 'py'.
 * - If the object is a function, returns 'fn' or 'class'
 *   if the function is a non-writable prototype, indicating an ES6 class.
 * - If the object is of type 'bigint', returns 'big'.
 * - If the object is null, returns 'void'.
 * - If the object is an object, returns 'obj'.
 * - If the object is a number, returns 'num'.
 * - If the object is a string, returns 'string'.
 * - If no other checks pass, the function returns undefiend.
 */
  function getType(obj) {
    if (obj?.ffid) return 'py';
    if (typeof obj === 'function') {
      if (obj.prototype) {
        const desc = Object.getOwnPropertyDescriptor(obj, 'prototype');
        if (!desc.writable) return 'class';
      }

      return 'fn';
    }
    if (typeof obj === 'bigint') return 'big';
    if (obj === null) return 'void';
    if (typeof obj === 'object') return 'obj';
    if (!isNaN(obj)) return 'num';
    if (typeof obj === 'string') return 'string';
  }

  /**
 * `Bridge` is a class that facilitates communications
 *  between Python and JavaScript.
 * It helps manage FFID map to JavaScript objects, construct a new PyBridge,
 * and handle inter-process communication (IPC) messages.
 *
 * @class
 *
 * @property {number} ffid - ID that increments each time a
 * new object is returned to Python.
 * @property {number} lastadd - The last added value.
 * @property {object} m - Contains a reference map
 * of FFIDs to JavaScript objects.
 * @property {IPCClass} ipc - Inter-process Communication.
 * @property {PyBridge} pyi - PyBridge.
 * @property {object} eventMap - Object to manage events.
 *
 */
  class Bridge {
  /**
   * Bridge class constructor. Initializes the ffid, lastadd,
   * reference map m, ipc, pyBridge and eventMap.
   *
   * Each operation that can be preformed by the python side
   * of the bridge will have a relevant function within this class.
   *
   * @param {IPCClass} ipc - Inter Process Communication
   */
    constructor(ipc) {
    // This is an ID that increments each time a new object is returned
    // to Python.
      this.ffid = 0;
      this.lastadd=0;
      // This contains a refrence map of FFIDs to JS objects.
      this.m = {
        0: {
          console,
          require: $require,
          _require: require,
          globalThis,
          RegExp,
          once,
          needsNodePatches: () => {
            const [major, minor] = process.versions.node.split('.');
          if ((major == 14 && minor < 17) || (major == 15)) { // eslint-disable-line
              return true;
            }
            return false;
          },
          async evaluateWithContext($block, $locals) {
            const $variables = Object.keys($locals);
            const $inputs = $variables.map((v) => `$locals["${v}"]`);
            const $code = (
            $block.split('\n').length === 1 &&
            !$block.includes('return ')
            ) ? 'return ' + $block : $block;
            const $finalCode = `(async (${
              $variables.join(', ')}
            ) => { ${$code} })(${$inputs.join(', ')})`;
            return await eval($finalCode);
          },
        },
      };
      this.ipc = ipc;
      this.pyi = new PyBridge(this.ipc, this);
      // Is eventMap used... anywhere?
      this.eventMap = {};

    // ipc.on('message', this.onMessage)
    }

    /**
   * Increments the last added ffid and
   * generates a snowflake integer with generated ffid
   *
   * @return {string} - Snowflake with incremented ffid
   */
    ffidinc() {
      const snow_ffid = generateSnowflake(++this.lastadd, SnowflakeMode.jsffid);
      this.ffid = snow_ffid;
      // console.log('ffid is now:', snow_ffid);
      return snow_ffid;
    }


    /**
   * Adds WeakRef of an object to the ffid map (m)
   *
   * @param {object} object - The object to create a weak reference of
   * @param {string} ffid - The ffid associated with the object
   *
   */
    addWeakRef(object, ffid) {
      const weak = new WeakRef(object);
      Object.defineProperty(this.m, ffid, {
        get() {
          return weak.deref();
        },
      });
    }
    /**
   * This function selects a request to send across the bridge
   * based on the type of object specified by the type parameter.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {object} v - Identifier of the object on the FFID map.
   * @param {string} type - type of object
   * @throws Will return ipc.send error message if any exception occurs.
   *  @return {void} nothing.
   */
    switchType(r, v, type) {
      switch (type) {
        case 'string': return {r, key: 'string', val: v};
        case 'big': return {r, key: 'big', val: Number(v)};
        case 'num': return {r, key: 'num', val: v};
        case 'py': return {r, key: 'py', val: v.ffid};
        case 'class':
          this.m[this.ffidinc()] = v;
          return {r, key: 'class', val: this.ffid};
        case 'fn':
          this.m[this.ffidinc()] = v;
          return {r, key: 'fn', val: this.ffid};
        case 'obj':
          this.m[this.ffidinc()] = v;
          let thiskey='obj';
          if (v instanceof EventEmitter) {
            thiskey='obje';
          }
          return {r, key: thiskey, val: this.ffid};
        default: return {r, key: 'void', val: this.ffid};
      }
    }
    /**
   * Asynchronously retrieves every single value from the
   * specified object in the FFID map and sends it back across
   * the bridge.
   *
   * @async
   * @param {int} r - The request identifier.
   * @param {int} ffid - The identifier of the object on the FFID map.
   * @param {string} attr - The attribute to retrieve from the object.
   * @throws Will return ipc.send void message with ffid if an error occurs.
   *  @return {void} nothing.
   */
    async getdeep(r, ffid) {
      try {
        var to_return=[];
        for (const attribute in this.m[ffid]) {
          if (this.m[ffid][attribute] !=null) {
            // console.log(attribute + ': ' + obj[attribute]);
            var v = await this.m[ffid][attribute];
            var type = v.ffid ? 'py' : getType(v);
            var attObj=this.switchType(r, v, type);
            attObj['attr']=attribute;
            if (autoInspect) {
              attObj['insp']=util.inspect(v, {});
            }
            to_return.push(attObj);
          }
        }
        return this.ipc.send({r, key: 'deepobj', val: to_return});
      } catch (e) {
        return this.ipc.send({r, key: 'void', val: this.ffid});
      }
      // return this.switchType(r, v, type);
    }
    /**
   * Asynchronously retrieves the value of a specific attribute for
   * a specified object in the FFID map and sends it back across
   * the bridge.
   *
   * @async
   * @param {int} r - The request identifier.
   * @param {int} ffid - The identifier of the object on the FFID map.
   * @param {string} attr - The attribute to retrieve from the object.
   * @throws Will return ipc.send void message with ffid if an error occurs.
   *  @return {void} nothing.
   */
    async get(r, ffid, attr) {
      try {
        var v = await this.m[ffid][attr];
        var type = v.ffid ? 'py' : getType(v);
      } catch (e) {
        return this.ipc.send({r, key: 'void', val: this.ffid});
      }
      const attObj=this.switchType(r, v, type);
      if (autoInspect) {
        attObj['insp']=util.inspect(v, {});
      }

      return this.ipc.send(attObj);
    }

    /**
   * Sets the value of a specific attribute of
   *  a specified object in the FFID map.
   *
   * @param {int} r - Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @param {string} attr - Attribute of the object to set.
   * @param {Array} val - Array containing the value to set.
   * @return {void} nothing.
   */
    set(r, ffid, attr, [val]) {
      try {
        this.m[ffid][attr] = val;
      } catch (e) {
        return this.ipc.send({r, key: 'error', error: e.stack});
      }
      this.ipc.send({r, key: '', val: true});
    }

    /**
   * Initializes an instance of a class using the "new" keyword,
   *  r just call the function. The specified class or function is
   * retrieved from a specified object in the FFID map.
   *
   * @param {int} r - Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @param {string} attr - Name of the class/function/constructor
   * to call with new keyword.
   * @param {Array} args - Array containing arguments to pass
   * to constructor/function.
   */
    init(r, ffid, attr, args) {
      const generatedIdentifer = this.ffidinc();
      this.m[generatedIdentifer] = attr?
     new this.m[ffid][attr](...args):
     new this.m[ffid](...args);
      // console.log('init', r, ffid, attr, args, this.ffid,  this.m[this.ffid])
      let attrObj={};
      if (this.m[this.ffid] instanceof EventEmitter) {
        attrObj={r, key: 'inste', val: this.ffid};
      } else {
        attrObj={r, key: 'inst', val: this.ffid};
      }
      if (autoInspect) {
        attrObj['insp']=util.inspect(this.m[this.ffid], {});
      }
      this.ipc.send(attrObj);
    }
    /**
   * This function handles the synchronous or asynchronous
   * method calls on the provided object.
   * If an exception is encountered during method call,
   * it sends IPC communication with error details.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @param {string} attr - Name of the method to call on the object.
   * @param {Array} args - Array containing arguments to
   * pass to the function/method.
   * @throws Will return ipc.send error message if any exception occurs.
   *  @return {void} nothing.
   */
    async call(r, ffid, attr, args) {
      try {
        if (attr) {
          var v = await this.m[ffid][attr].apply(this.m[ffid], args) // eslint-disable-line
        } else {
          var v = await this.m[ffid](...args) // eslint-disable-line
        }
      } catch (e) {
        return this.ipc.send({r, key: 'error', error: e.stack});
      }
      const type = getType(v);
      // console.log('GetType', type, v);
      const attrObj=this.switchType(r, v, type);
      if (autoInspect) {
        attrObj['insp']=util.inspect(v, {});
      }
      return this.ipc.send(attrObj);
    }

    /**
   * This function calls the inspect util function
   * on the provided object for debugging.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @param {string} mode - Mode for util.inspect.
   * @return {void} nothing.
   */
    async inspect(r, ffid, mode) {
      const colors = supportsColors && (mode === 'str');
      const s = util.inspect(await this.m[ffid], {colors});
      this.ipc.send({r, val: s});
    }

    /**
   * This asynchronous function converts the provided
   * object to json string and sends it over IPC.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @return {void} nothing.
   */
    async serialize(r, ffid) {
      const v = await this.m[ffid];
      this.ipc.send({r, val: v.valueOf()});
    }
    /**
   * This asynchronous function gthe provided
   * object to json string and sends it over IPC.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @return {void} nothing.
   */
    async blob(r, ffid) {
      const v = await this.m[ffid];

      // The result property contains the data URL
      const blobContent = v;

      // Step 2: Convert Blob to Buffer (if necessary)
      // eslint-disable-next-line max-len
      const bufferData = Buffer.isBuffer(blobContent) ? blobContent : Buffer.from(blobContent);

      // Step 3: Encode Buffer to Base64
      const base64Data = bufferData.toString('base64');
      this.ipc.send({r, length: v.length, blob: base64Data});
      // Convert the JSON object to a string


      // Create a FileReader object
    }

    /**
   * This function fetches the keys of the provided
   * object and sends them over IPC.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @return {void} nothing.
   */
    async keys(r, ffid) {
      const v = await this.m[ffid];
      const keys = Object.getOwnPropertyNames(v);
      this.ipc.send({r, keys});
    }

    /**
   * This function is called to gracefully terminate the JavaScript process.
   *
   * @async
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @return {void} nothing.
   */
    async shutdown(r, ffid) {
      process.exit();
    }

    /**
   * This function is called to de-reference the
   * objects in the FFID map for garbage collection.
   *
   * @param {int} r -  Request identifier.
   * @param {int} ffid - Identifier of the object on the FFID map.
   * @param {string} attr - Currently not used parameter.
   * @param {Array} args - Array which contains
   * identifiers of objects to de-reference.
   * @return {void} nothing.
   */
    free(r, ffid, attr, args) {
      for (const id of args) {
        delete this.m[id];
      }
    }
    /**
   * Handles the process of making python objects.
   * @param {integer} r - a request sender identifier
   * @param {Array} args - function arguments
   */
    make_python_proxys(r, args) {
      const made = {};
      let madeCount = 0;

      /**
     * Parse input arguments to make Python objects
     * @param {object} input - input object to parse
     */
      const parse = (input) => {
        if (typeof input !== 'object') return;
        for (const k in input) {
          if (input.hasOwnProperty(k)) {
            const v = input[k];
            if (v && typeof v === 'object') {
              if (v.r && v.ffid === '') {
                this.ffidinc();
                const proxy = this.pyi.makePyObject(this.ffid);
                this.m[this.ffid] = proxy;
                made[input[k].r] = this.ffid;
                input[k] = proxy;
                madeCount++;
              } else if (v.ffid) {
                input[k] = this.m[v.ffid];
              } else {
                parse(v);
              }
            } else {
              parse(v);
            }
          }
        }
      };
      parse(args);

      // We only need to reply if we made some Proxies
      if (madeCount) this.ipc.send({r, key: 'pre', val: made});
    }

    /**
   * Handles incoming messages and processes accordingly.
   * @param {object} param0 - A destructured object containing
   *  r (an integer), action (a string), p (a boolean),
   *  ffid (a string), key (a string), args (an array)
   */
    async onMessage({r, action, p, ffid, key, args}) {
    // console.log('onMessage!',  r, action, p, ffid, key, args)
      try {
        if (p) {
          this.make_python_proxys(r + 1, args);
        }
        await this[action](r, ffid, key, args);
      } catch (e) {
        return this.ipc.send({r, key: 'error', error: e.stack});
      }
    }
  }

  Object.assign(util.inspect.styles, {
    bigint: 'yellow',
    boolean: 'yellow',
    date: 'magenta',
    module: 'underline',
    name: 'blueBright',
    null: 'bold',
    number: 'yellow',
    regexp: 'red',
    special: 'magentaBright', // (e.g., Proxies)
    string: 'green',
    symbol: 'blue',
    undefined: 'grey',
  });

  const handlers = {};
  /**
 * The IPCClass sends data to Python through stderr/.
 * It provides methods to send data,
 * write Raw data and handle the Inter-process Communication (IPC) messages.
 * @class
 */
  class IPCClass {
  /**
   * IPCClass's constructor. Sets up the process for IPC.
   *
   * @param {Process} tgprocess - The process for IPC to use.
   */
    constructor(tgprocess) {
      this.process = tgprocess;
      // this.message='';
      this.queue=new AsyncQueue();
    }

    /**
   * Send method writes JSON stringified data to the
   * process' stderr and log to debug console with 'js -> py' label.
   * @param {any} data - The data user want to write to the process' stderr
   */
    send = (data) => {
      debug('js -> py', data);
      this.process.stderr.write(JSON.stringify(data) + '\n');
    };

    /**
   * writeRaw method writes the data to the process'
   * stderr and log to debug console with 'js -> py' label,
   * also it store the callback function into the handlers object with index 'r'
   * for the further IPC message processing.
   * @param {any} data - The data user want to write to stderr.
   * @param {number} r - The index user want to store the callback function.
   * @param {function} cb - The callback function user want to store.
   */
    writeRaw = (data, r, cb) => {
      debug('js -> py', data);
      handlers[r] = cb;
      this.process.stderr.write(data + '\n');
    };
    /**
   * The 'write' method stores the callback function into the handlers
   * object with key 'data.r', and utilizes the 'send' method
   * to write data to stderr.
   * @param {any} data - Data to write to stderr.
   * @param {function} cb - Callback function to store.
   */
    write = (data, cb) => {
      handlers[data.r] = cb;
      this.send(data);
    };

    /**
   * Parses lines of a message on the bridge,
   * identifying and actioning upon JSON-parsable lines
   * If a line contains a JSON object with a
   * attribute 'c' that is equal to 'pyi',
   * it executes a function from the handlers object
   * with the attribute 'r' of the JSON object as key
   * If the action for 'c' is anything but 'pyi',
   * the JSON object is handled by
   * calling onMessage method of the bridge object
   *
   * @param {Bridge} bridge - An instance of the Bridge class
   */
    handle_message =(bridge)=>{
      while (this.queue.hasElements()) {
        const message=this.queue.dequeue();
        for (const line of message.split('\n')) {
          try {
            var j = JSON.parse(line);
          } catch (e) {
            continue;
          }
          if (j.c === 'pyi') {
            handlers[j.r]?.(j);

            if (handlers.hasOwnProperty(j.r)) {
              delete handlers[j.r];
            }
          } else {
            bridge.onMessage(j);
          }
        }
      }
    };
    /**
   * Handles the operation of reading a data stream.
   *
   * @param {string} data - The data stream to read.
   * @param {Bridge} bridge - An instance of the Bridge class.
   */
    read = (data, bridge) => {
      const d = String(data);
      let message='';
      for (let i = 0; i < d.length; i++) {
        if (d[i] === '\n') {
          debug('py -> js', message);
          this.queue.enqueue(message);
          this.handle_message(bridge);
          message = '';
        } else {
          message += d[i];
        }
      }
      this.queue.enqueue(message);
    };
    /**
   * Handles the end of data stream operations.
   *
   * IE, Flush the last line.
   *
   * @param {Bridge} bridge - An instance of the Bridge class.
   */
    end = (bridge)=>{
      if (this.queue.hasElements()) {
        debug('py -> js', this.queue.peek());
        this.handle_message(bridge);
      }
    };
  }


  const ipc = new IPCClass(process);
  const bridge = new Bridge(ipc);

  process.stdin.on('data', (data) => {
    ipc.read(data, bridge);
  });

  // flush last line
  process.stdin.on('end', () => {
    ipc.end(bridge);
  });

  process.on('exit', () => {
    console.log(`Shutting down node js process ${process.pid}.`);
  });
} catch (e) {
  const data={r: 404, key: 'error_severe', error_severe: e.stack};
  process.stderr.write(JSON.stringify(data) + '\n');
}
