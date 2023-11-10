from javascriptasync import init_js, require
init_js()

lodash=require('lodash')
print('loadashed')
#This code won't work.
examplejs = require('./jsvalue.js')
print(examplejs.greet())
