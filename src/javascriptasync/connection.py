import asyncio
import threading, subprocess, json, time, signal
import atexit, os, sys
from . import config
from .logging import logs, log_print
ISCLEAR=False
ISNOTEBOOK=False
try:
    from IPython import get_ipython
    if "COLAB_GPU" in os.environ:
        isclear= True
    else:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            ISNOTEBOOK= True
except Exception:
    ISCLEAR= False
# The "root" interface to JavaScript with FFID 0


class ConnectionClass():
    #Encapsulated connection to make this file easier to work with.
    # Special handling for IPython jupyter notebooks
    stdout = sys.stdout
    notebook = False
    NODE_BIN = getattr(os.environ, "NODE_BIN") if hasattr(os.environ, "NODE_BIN") else "node"
    dn = os.path.dirname(__file__)
    proc = None
    com_thread = None
    stdout_thread = None


    sendQ = []

    def is_notebook(self):
        return ISNOTEBOOK

        

    def __init__(self,config:config.JSConfig):
        self.config=config
        # Modified stdout
        self.killlock=threading.Lock()
        self.endself=False
        self.modified_stdout = (sys.stdout != sys.__stdout__) or (getattr(sys, 'ps1', sys.flags.interactive) == '>>> ')

        if self.is_notebook() or self.modified_stdout:
            self.notebook = True
            self.stdout = subprocess.PIPE
        if self.supports_color():
            os.environ["FORCE_COLOR"] = "1"
        else:
            os.environ["FORCE_COLOR"] = "0"
        # Make sure our child process is killed if the parent one is exiting
        atexit.register(self.stop)

    def supports_color(self):
        """
        Returns True if the running system's terminal supports color, and False
        otherwise.
        """
        plat = sys.platform
        supported_platform = plat != "Pocket PC" and (plat == "win32" or "ANSICON" in os.environ)
        # isatty is not always implemented, #6223.
        is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        if 'idlelib.run' in sys.modules:
            return False
        if self.notebook and not self.modified_stdout:
            return True
        return supported_platform and is_a_tty


    

    # Currently this uses process standard input & standard error pipes
    # to communicate with JS, but this can be turned to a socket later on
    # ^^ Looks like custom FDs don't work on Windows, so let's keep using STDIO.

    

    def read_stderr(self,stderrs):
        ret = []
        for stderr in stderrs:
            inp = stderr.decode("utf-8")
            for line in inp.split("\n"):
                if not len(line):
                    continue
                if not line.startswith('{"r"'):
                    print("[JSE]", line)
                    continue
                try:
                    d = json.loads(line)
                    logs.debug("%s,%d,%s","connection: [js -> py]", int(time.time() * 1000), line)
                    ret.append(d)
                except ValueError as e:
                    print("[JSE]", line)
        return ret

    # Write a message to a remote socket, in this case it's standard input
    # but it could be a websocket (slower) or other generic pipe.
    def writeAll(self,objs):
        for obj in objs:
            if type(obj) == str:
                j = obj + "\n"
            else:
                j = json.dumps(obj) + "\n"
            logs.debug("connection: %s,%d,%s","[py -> js]", int(time.time() * 1000), j)
            
            #log_print('procstatus',self.proc)
            if not self.proc:
                self.sendQ.append(j.encode())
                continue
            try:
                # Iterate over all attributes of the instance
                #for attribute, value in vars(self.proc).items():  log_print(f"Attribute: {attribute}, Value: {value}")
                self.proc.stdin.write(j.encode())
                self.proc.stdin.flush()
            except Exception:
                self.stop()
                break


    stderr_lines = []

    # Reads from the socket, in this case it's standard error. Returns an array
    # of responses from the server.
    def readAll(self):
        ret = self.read_stderr(self.stderr_lines)
        self.stderr_lines.clear()
        return ret

    
    def com_io(self):
        
        try:
            if os.name == 'nt' and 'idlelib.run' in sys.modules:
                logs.debug('subprossess mode s')
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.dn + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE,
                    creationflags = subprocess.CREATE_NO_WINDOW
                )
            else:
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.dn + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE
                )

        except Exception as e:
            print(
                "--====--\t--====--\n\nBridge failed to spawn JS process!\n\nDo you have Node.js 16 or newer installed? Get it at https://nodejs.org/\n\n--====--\t--====--"
            )
            self.stop()
            raise e

        for send in self.sendQ:
            self.proc.stdin.write(send)
        self.proc.stdin.flush()

        if self.notebook:
            self.stdout_thread = threading.Thread(target=self.stdout_read, args=(), daemon=True)
            self.stdout_thread.start()

        while self.proc.poll() == None:
            
            #self.killlock.acquire()
            #log_print('killlock checking for input')
            readline=self.proc.stderr.readline()
            self.stderr_lines.append(readline)
            self.config.event_loop.queue.put("stdin")
            
            #log_print('killlock release for input')
            #self.killlock.release()

        self.stop()


    def stdout_read(self):
        while self.proc.poll() is None:

            if not self.endself:
                #log_print('kill')
                print(self.proc.stdout.readline().decode("utf-8"))


    def start(self):
        logs.info("ConnectionClass.com_thread opened")
        self.com_thread = threading.Thread(target=self.com_io, args=(), daemon=True)
        self.com_thread.start()


    def stop(self):
        
        self.endself=True
        
        time.sleep(4)
        
        print('terminating.')
        try:
            #log_print('STOP.')
            self.proc.terminate()
        except Exception as e:
            raise e
        self.config.reset_self()



    def is_alive(self):
        return self.proc.poll() is None


DUMMYc=True