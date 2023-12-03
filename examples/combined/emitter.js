/* eslint-disable require-jsdoc */
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
module.exports = MyEmitter;
