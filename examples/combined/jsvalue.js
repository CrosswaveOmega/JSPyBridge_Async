/* eslint-disable require-jsdoc */
const lodash = require('lodash');
function greet() {
  const numbers = [1, 5, 3, 7, 2, 8, 4, 6];

  const maxNumber = lodash.max(numbers);

  console.log('The maximum number is:', maxNumber);
}

module.exports = {greet};
