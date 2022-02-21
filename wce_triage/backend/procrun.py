from queue import Queue
import threading

class Process_Communicator():

    def join(self):
        self.s_err.join()
        self.s_out.join()
        self.running = False
        self.aggregator.join()
        self.ti.join()

    def enqueue_in(self):
        while self.running and self.subproc.stdin is not None:
            while not self.q_in.empty():
                s = self.q_in.get()
                self.subproc.stdin.write(str(s) + '\n\r')
            pass

    def enqueue_output(self):
        if not self.subproc.stdout or self.subproc.stdout.closed:
            return
        out = self.subproc.stdout
        for line in iter(out.readline, b''):
            self.q_out.put(line)
        #    out.flush()

    def enqueue_err(self):
        if not self.subproc.stderr or self.subproc.stderr.closed:
            return
        err = self.subproc.stderr
        for line in iter(err.readline, b''):
            self.q_err.put(line)

    def aggregate(self):
        while (self.running):
            self.update()
        self.update()

    def update(self):
        line = ""
        try:
            while self.q_err.not_empty:
                line = self.q_err.get_nowait()  # or q.get(timeout=.1)
                self.unbblocked_err += line
        except Queue.Empty:
            pass

        line = ""
        try:
            while self.q_out.not_empty:
                line = self.q_out.get_nowait()  # or q.get(timeout=.1)
                self.unbblocked_out += line
        except Queue.Empty:
            pass

        while not self.q_in.empty():
                s = self.q_in.get()
                self.subproc.stdin.write(str(s))

    def get_stdout(self, clear=True):
        ret = self.unbblocked_out
        if clear:
            self.unbblocked_out = ""
        return ret

    def has_stdout(self):
        ret = self.get_stdout(False)
        if ret == '':
            return None
        else:
            return ret

    def get_stderr(self, clear=True):
        ret = self.unbblocked_out
        if clear:
            self.unbblocked_out = ""
        return ret

    def has_stderr(self):
        ret = self.get_stdout(False)
        if ret == '':
            return None
        else:
            return ret

    def __init__(self, subproc):
        '''This is a simple class that collects and aggregates the
        output from a subprocess so that you can more reliably use
        the class without having to block for subprocess.communicate.'''
        self.subproc = subproc
        self.unbblocked_out = ""
        self.unbblocked_err = ""
        self.running = True
        self.q_out = Queue.Queue()
        self.s_out = threading.Thread(name="out_read",
                                      target=self.enqueue_output,
                                      args=())
        self.s_out.daemon = True  # thread dies with the program
        self.s_out.start()

        self.q_err = Queue.Queue()
        self.s_err = threading.Thread(name="err_read",
                                      target=self.enqueue_err,
                                      args=())
        self.s_err.daemon = True  # thread dies with the program
        self.s_err.start()

        self.q_in = Queue.Queue()
        self.aggregator = threading.Thread(name="aggregate",
                                           target=self.aggregate,
                                           args=())
        self.aggregator.daemon = True  # thread dies with the program
        self.aggregator.start()
        pass