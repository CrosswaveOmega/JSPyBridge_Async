import javascriptasync
javascriptasync.init_js()

class MyOtherObject():
    def __init__(self) -> None:
        self.myArray=[]
    def append(self,i):
        self.myArray.append(i)

countUntil = 9
myObject = { 'hello': '','mylist':[1,4]}
otherobj=MyOtherObject()
overevt=javascriptasync.require('./over.js')

result=overevt.overevent(myObject,countUntil, otherobj)
print(countUntil,myObject,otherobj.myArray)