from __future__ import annotations
from queue import Empty, Queue

# import asyncio
import threading
import subprocess
import json
import time

# import signal
import atexit
import os
import sys
from typing import Any, Dict, List, TextIO, Union
from . import config, events
from .core.jslogging import log_print, log_debug, log_info, log_error, log_critical, log_warning
from .util import haspackage
from .errors import InvalidNodeJS
from .json_patch import JSONRequestDecoder

ISCLEAR = False
ISNOTEBOOK = False
try:
    if haspackage("IPython"):
        from IPython import get_ipython

        if "COLAB_GPU" in os.environ:
            ISCLEAR = True
        else:
            if (get_ipython().__class__.__name__) == "ZMQInteractiveShell":
                ISNOTEBOOK = True
    else:
        ISCLEAR = False
except (ImportError, KeyError, AttributeError) as pre_error:
    log_error(pre_error)
    ISCLEAR = False

# The "root" interface to JavaScript with FFID 0


class ConnectionClass:
    """
    Encapsulated connection class for interacting with JavaScript.

    This class initalizes a node.js instance, sends information from Python to JavaScript, and recieves input from JavaScript back to Python.

    Attributes:
        config (config.JSConfig): Reference to the active JSConfig object.
        event_loop(config.JSConfig): Reference to the event_loop
        endself(bool): if the thread is ending, send nothing else.
        stdout (TextIO): The standard output.
        modified_stdout (bool): True if stdout has been altered in some way, False otherwise.
        notebook (bool): True if running in a Jupyter notebook, False otherwise.
        NODE_BIN (str): The path to the Node.js binary.
        directory_name (str): The directory containing this file.
        proc (subprocess.Popen): The subprocess for running JavaScript.
        com_thread (threading.Thread): The thread for handling communication with JavaScript.
        stdout_thread (threading.Thread): The thread for reading standard output.

        sendQ (list): Queue for outgoing messages to JavaScript.
        stderr_lines (list): Lines piped from JavaScript Process
    """

    # Encapsulated connection to make this file easier to work with.
    # Special handling for IPython jupyter notebooks

    def is_notebook(self):
        """
        Check if running in a Jupyter notebook.

        Returns:
            bool: True if running in a notebook, False otherwise.
        """
        return ISNOTEBOOK

    def __init__(self, configval: config.JSConfig):
        """
        Initialize the ConnectionClass.

        Args:
            config (config.JSConfig): Reference to the active JSConfig object.
        """

        self.stdout: TextIO = sys.stdout

        self.notebook = False
        self.NODE_BIN = os.environ.get("NODE_BIN") if hasattr(os.environ, "NODE_BIN") else "node"
        self.check_nodejs_installed()

        self.directory_name: str = os.path.dirname(__file__)
        self.proc: subprocess.Popen = None
        self.com_thread: threading.Thread = None
        self.stdout_thread: threading.Thread = None
        #self.stderr_lines: List[str] = []
        self.stderr_lines: Queue[str] = Queue()
        self.sendQ: list = []
        self.config: config.JSConfig = configval
        self.event_loop: events.EventLoop = None
        # Modified stdout
        self.endself = False
        self.modified_stdout = (sys.stdout != sys.__stdout__) or (getattr(sys, "ps1", sys.flags.interactive) == ">>> ")

        if self.is_notebook() or self.modified_stdout:
            self.notebook = True
            self.stdout = subprocess.PIPE

        self.earlyterm = False

        atexit.register(self.stop)

    def check_nodejs_installed(self):
        """Check if node.js is installed.

        Raises:
            InvalidNodeJS: Node.JS was not installed.
        """

        try:
            output = subprocess.check_output([self.NODE_BIN, "-v"])
            print("NodeJS is installed: Current Version Node.js version:", output.decode().strip())
        except OSError as e:
            errormessage = (
                "COULD NOT FIND A VALID NODE.JS INSTALLATION!" + "PLEASE INSTALL NODE.JS FROM https://nodejs.org/  "
            )
            log_critical(errormessage)
            raise InvalidNodeJS(errormessage) from e

    def supports_color(self) -> bool:
        """
        Returns True if the running system's terminal supports color, and False
        otherwise.
        """
        plat = sys.platform
        supported_platform = plat != "Pocket PC" and (plat == "win32" or "ANSICON" in os.environ)
        # isatty is not always implemented, #6223.
        is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        if "idlelib.run" in sys.modules:
            return False
        if self.notebook and not self.modified_stdout:
            return True
        return supported_platform and is_a_tty

    # Currently this uses process standard input & standard error pipes
    # to communicate with JS, but this can be turned to a socket later on
    # ^^ Looks like custom FDs don't work on Windows, so let's keep using STDIO.
    def read_output_line(self, out_line:str):
        """
        Process an output line from the JavaScript process, returning a list of JSON-decoded
        data objects. The line is decoded using UTF-8, then split into individual lines based
        on newline characters. Empty lines are skipped.


        In case of a ValueError during JSON decoding, the error and offending line are printed.

        Args:
            out_line (str): The output line to be processed.

        Returns:
            list: A list of JSON-decoded data objects derived from the input line.

        Raises:
            ValueError: If a line cannot be JSON-decoded.
        """
        inp = out_line.decode("utf-8")
        ret=[]
        for line in inp.split("\n"):
            if not len(line):
                continue
            #this line worries me.
            decoder=JSONRequestDecoder()
            try:
                d,decodeok=decoder.decode(line)
                if not decodeok:
                    print("[JSE]", line)
                    continue
                
                log_debug("%s,%d,%s", "connection: [js -> py]", int(time.time() * 1000), line)
                ret.append(d)
            except json.JSONDecodeError as jde:
                print(jde, "[JSE]", line)
            except ValueError as v_e:
                print(v_e, "[JSE]", line)
            
                #log_error()
        return ret
    def read_stderr(self) -> List[Dict]:
        """
        Read and process stderr messages from the node.js process, transforming them
        into Dictionaries via json.loads


        Returns:
            List[Dict]: Processed outbound_messages
        """
        out=[]
        current_iter=0
        still_full=True
        while (self.stderr_lines.qsize()>0 and still_full):
            try:
                toadd=self.stderr_lines.get_nowait()
                out.extend(self.read_output_line(toadd))
                current_iter+=1
            except Empty as e:
                log_warning("EventLoop, inbound Queue is empty.",exc_info=e)
                still_full=False
        return out

    # Write a message to a remote socket, in this case it's standard input
    # but it could be a websocket (slower) or other generic pipe.
    def writeAll(self, objs: List[Union[str, Any]]):
        """
        Transform objects into JSON strings, and write them to the node.js process.

        Args:
            objs (List[Union[str,Any]]): List of messages to be transformed and sent.
        """
        for obj in objs:
            if type(obj) == str:
                j = obj + "\n"
            else:
                
                if not type(obj) == dict:  
                    pass
                    # print(obj.ffid)
                j = json.dumps(obj) + "\n"
            log_debug("connection: %s,%d,%s", "[py -> js]", int(time.time() * 1000), j)
            encoded=j.encode()
            # log_print('procstatus',self.proc)
            if not self.proc:
                self.sendQ.append(j.encode())
                continue
            try:
                self.proc.stdin.write(encoded)
                self.proc.stdin.flush()
            except (IOError, BrokenPipeError) as error:
                log_critical(encoded)
                log_critical(error, exc_info=True)
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
        ret = self.read_stderr()
        # self.stderr_lines.clear()
        return ret

    def startup_node_js(self):
        try:
            if os.name == "nt" and "idlelib.run" in sys.modules:
                log_debug("subprossess mode s")
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.directory_name + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.directory_name + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE,
                )

        except subprocess.SubprocessError as err:
            log_critical(
                "--====--\t--====--\n\nBridge failed to spawn JS process!\n\nDo you have Node.js 16 or newer installed? Get it at https://nodejs.org/\n\n--====--\t--====--"
            )
            self.stop()
            raise err
        
    def recieve_stdio(self,line_read):
        """
        Receives standard input from a subprocess pipe and adds it to a
        queue for further processing. It also raises a 'stdin' event.

        Args:
            stderr(subprocess.PIPE): A subprocess pipe from which to read.
        """
        readline = line_read
        if readline:
            self.stderr_lines.put(readline)
            self.event_loop.queue.put("stdin")


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

        print("Starting Node.JS connection...!")
        self.startup_node_js()
        for send in self.sendQ:
            self.proc.stdin.write(send)
        self.proc.stdin.flush()
        print("Connection established!")
        if self.notebook:
            self.stdout_thread = threading.Thread(target=self.stdout_read, args=(), daemon=True)
            self.stdout_thread.start()

        while self.proc.poll() is None:
            self.recieve_stdio(self.proc.stderr.readline())
            

        print("Termination condition", self.endself)
        if not self.endself:
            print("early terminate")
            self.earlyterm = True
            self.stop()

    def stdout_read(self):
        """
        Read and process standard output from the JavaScript process.
        This is only for Jupyter notebooks.
        """
        while self.proc.poll() is None:
            if not self.endself:
                # log_print('kill')
                print(self.proc.stdout.readline().decode("utf-8"))

    def start(self):
        """
        Start the communication thread.
        """
        log_info("ConnectionClass.com_thread opened")
        self.event_loop=self.config.get_event_loop()
        self.com_thread = threading.Thread(target=self.com_io, args=(), daemon=True)
        self.com_thread.start()

    def stop(self):
        """
        Terminate the node.js process.
        """
        if self.earlyterm:
            print("Early Termination, stopping.")
            return
        self.endself = True
        time.sleep(2)
        log_print("terminating JS connection..")
        try:
            self.proc.terminate()
            print("Terminated JS Runtime.")

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
