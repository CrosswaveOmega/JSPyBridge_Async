
#importing importlib.util module
import importlib.util
#importing the system module
import sys
def haspackage(name:str):
    #code to check if the library exists
    if (spec := importlib.util.find_spec(name)) is not None:
        return True
    #else displaying that the module is absent
    else:
        return False
   
