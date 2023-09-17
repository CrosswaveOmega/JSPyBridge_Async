
from __future__ import annotations
import asyncio
import threading, subprocess, json, time, signal
import atexit, os, sys
from typing import Any, Dict, List, TextIO, Union
from . import config
from .logging import logs, log_print
from .util import haspackage
ISCLEAR=False
ISNOTEBOOK=False

try:
    if haspackage("IPython"):
        from IPython import get_ipython
        if "COLAB_GPU" in os.environ:
            ISCLEAR= True
        else:
            shell = get_ipython().__class__.__name__
            if shell == "ZMQInteractiveShell":
                ISNOTEBOOK= True
    else:
        ISCLEAR=False
except Exception as s:
    ISCLEAR= False
# The "root" interface to JavaScript with FFID 0


class ConnectionClass():
    """
    Encapsulated connection class for interacting with JavaScript.

    This class manages the communication between Python and JavaScript.

    Attributes:
        config (config.JSConfig): Reference to the active JSConfig object.
        endself(bool): if the thread is ending, send nothing else.
        stdout (TextIO): The standard output.
        modified_stdout (bool): True if stdout has been altered in some way, False otherwise.
        notebook (bool): True if running in a Jupyter notebook, False otherwise.
        NODE_BIN (str): The path to the Node.js binary.
        dn (str): The directory containing this file.
        proc (subprocess.Popen): The subprocess for running JavaScript.
        com_thread (threading.Thread): The thread for handling communication with JavaScript.
        stdout_thread (threading.Thread): The thread for reading standard output.
        sendQ (list): Queue for outgoing messages to JavaScript.
        stderr_lines (list): Lines piped from JavaScript Process
    """
    #Encapsulated connection to make this file easier to work with.
    # Special handling for IPython jupyter notebooks


    def is_notebook(self):
        """
        Check if running in a Jupyter notebook.

        Returns:
            bool: True if running in a notebook, False otherwise.
        """
        return ISNOTEBOOK

        

    def __init__(self,configval:config.JSConfig):
        """
        Initialize the ConnectionClass.

        Args:
            config (config.JSConfig): Reference to the active JSConfig object.
        """
        self.stdout:TextIO = sys.stdout
        self.notebook = False
        self.NODE_BIN = getattr(os.environ, "NODE_BIN") if hasattr(os.environ, "NODE_BIN") else "node"
        self.dn = os.path.dirname(__file__)
        self.proc:subprocess.Popen = None
        self.com_thread:threading.Thread = None
        self.stdout_thread:threading.Thread = None
        self.stderr_lines:List = []
        self.sendQ:list = []
        self.config:config.JSConfig=configval
        # Modified stdout
        self.endself=False
        self.modified_stdout = (sys.stdout != sys.__stdout__) or (getattr(sys, 'ps1', sys.flags.interactive) == '>>> ')

        if self.is_notebook() or self.modified_stdout:
            self.notebook = True
            self.stdout = subprocess.PIPE
        #I don't want to forcefully change os env settings.
        # if self.supports_color():
        #     os.environ["FORCE_COLOR"] = "1"
        # else:
        #     os.environ["FORCE_COLOR"] = "0"
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

    

    def read_stderr(self,stderrs:List[str])->List[Dict]:
        """
        Read and process stderr messages from the node.js process, transforming them
        into Dictionaries via json.loads

        Args:
            stderrs (List[str]): List of error messages.

        Returns:
            List[Dict]: Processed error messages.
        """
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
                except ValueError as v_e:
                    print(v_e,"[JSE]", line)
        return ret

    # Write a message to a remote socket, in this case it's standard input
    # but it could be a websocket (slower) or other generic pipe.
    def writeAll(self,objs:List[Union[str,Any]]):
        """
        Write messages to the node.js process.

        Args:
            objs (List[Union[str,Any]]): List of messages to be sent.
        """
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
            except Exception as error:
                logs.critical(error,exc_info=True)
                self.stop()
                break



    # Reads from the socket, in this case it's standard error. Returns an array
    # of responses from the server.
    def readAll(self):
        """
        Read and process all messages from the node.js process.

        Returns:
            list: Processed messages.
        """
        ret = self.read_stderr(self.stderr_lines)
        self.stderr_lines.clear()
        return ret

    
    def com_io(self):
        """
        Handle communication with the node.js process.

        This method runs as an endless daemon thread, initializing a Node.js
        instance and managing the piping of input and output between Python and
        JavaScript. It launches a new daemon thread using `com_io` as the
        function.

        The node.js process is spawned with the specified Node.js binary and
        a bridge script, which facilitates communication.

        Raises:
            Exception: If there's an issue spawning the JS process or if any
            exceptions occur during communication.
        """
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
            
            readline=self.proc.stderr.readline()
            self.stderr_lines.append(readline)
            self.config.event_loop.queue.put("stdin")
            
        print("Termination condition", self.endself)
        if not self.endself:
            self.stop()


    def stdout_read(self):
        """
        Read and process standard output from the JavaScript process.
        This is only for Jupyter notebooks.
        """
        while self.proc.poll() is None:

            if not self.endself:
                #log_print('kill')
                print(self.proc.stdout.readline().decode("utf-8"))


    def start(self):
        """
        Start the communication thread.
        """
        logs.info("ConnectionClass.com_thread opened")
        self.com_thread = threading.Thread(target=self.com_io, args=(), daemon=True)
        self.com_thread.start()


    def stop(self):
        """
        Terminate the node.js process.
        """
        self.endself=True
        time.sleep(2)
        log_print('terminating JS connection..')
        try:
            self.proc.terminate()
            print('Terminated JS Runtime.')
            time.sleep(3)
            print('Killing JS runtime.')
            self.proc.kill()
            
        except Exception as e:
            raise e
        self.config.reset_self()



    def is_alive(self):
        """
        Check if the node.js process is still running.

        Returns:
            bool: True if the process is running, False otherwise.
        """
        return self.proc.poll() is None
