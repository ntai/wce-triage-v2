import threading
import json
import traceback
from .emitter import Emitter
from queue import SimpleQueue
from typing import Optional
from collections import deque
import subprocess
from ..lib.util import get_triage_logger
from .models import Model


class ThreadedPipeReader(threading.Thread):
    def __init__(self, pipe, tag=None, encoding='iso-8859-1'):
        self.encoding = encoding
        self.alive = True
        self.pipe = pipe
        self.fragments = deque()
        self.n_lines = 0
        self.tag = tag
        pass

    def run(self):
        while self.alive:
            ch = self.pipe.read(1)
            if ch == b'':
                # Pipe is closed.
                self.alive = False
            else:
                self.fragments.append(ch)
                if ch in ['\r', '\n']:
                    self.n_lines += 1
                    pass
                pass
            pass
        pass

    def reading(self):
        return self.pipe if self.alive else None

    def readline(self):
        if self.n_lines > 0:
            buffer = bytearray(len(self.fragments) + 1)
            for i in range(len(self.fragments)):
                buffer[i] = ord(self.fragments[i])
            pass
        buffer[len(self.fragments)] = ord(b'\n')
        self.fragments.clear()
        return buffer.decode(self.encoding)

    def flush(self):
        return self._flush_fragments()

    pass


class ThreadedCommandRunner(threading.Thread):
    queue: SimpleQueue
    process: Optional[subprocess.Popen]
    model: Model
    stdout: Optional[ThreadedPipeReader]
    stderr: Optional[ThreadedPipeReader]

    def __init__(self, model: Model, messenger):
        super().__init__(daemon=True)
        self.model = model
        self.queue = SimpleQueue()
        self.process = None
        self.logger = get_triage_logger()
        self.stdout = None
        self.stderr = None
        self.messenger = messenger
        pass

    def run(self):
        while True:
            meta, args = self.queue.get()
            try:
                self.run_process(meta, args)
            except:
                pass
            self.process = None
            pass
        pass

    def run_process(self, meta, args):
        tag = meta.pop("tag")
        devname = meta.get("devname")
        if devname:
            Emitter.send(tag, {"device": devname, "runStatus": "", "totalEstimate": 0, "tasks": []})

        self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = self.process.communicate()
        self.stdout = ThreadedPipeReader(out)
        self.stderr = ThreadedPipeReader(err)

        try:
            while self.process.returncode is None:
                self.process.poll()

                line = self.stdout.readline()
                if line == b'' or line is None:
                    break
                if line.strip() != '':
                    self.logger.debug("%s: '%s'" % (tag, line))
                    try:
                        self.model.set_model_data(json.loads(line))
                    except Exception as exc:
                        self.logger.info("%s: BAD LINE '%s'\n%s" % (tag, line, traceback.format_exc()))
                        self.messenger.note(line)
                        pass
                    pass
                pass
            if self.process.returncode is not 0:
                self.messenger.note("Restore failed with error code %d" % self.process.returncode)
                pass
            pass
        except:
            pass
        if devname:
            self.model.set_model_data({"device": ''})
            pass
        pass

    def is_running(self):
        # FIXME: this needs to be more accuarte.
        return self.process and self.process.returncode is None

    def terminate(self):
        if not self.is_running():
            return
        process = self.process
        self.process = None
        process.terminate()
        pass
    pass
