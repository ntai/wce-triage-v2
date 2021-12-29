import subprocess
import threading
import json
import traceback
from .emitter import Emitter
from queue import SimpleQueue
from typing import Optional

from ..lib.util import get_triage_logger

tlog = get_triage_logger()


class ThreadedCommandRunner(threading.Thread):
    queue: SimpleQueue
    process: Optional[subprocess.Popen]

    def __init__(self):
        super().__init__(daemon=True)
        self.queue = SimpleQueue()
        self.process = None
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

        try:
            while self.process.returncode is None:
                self.process.poll()

                line = self.process.stdout.readline()
                if line == b'' or line is None:
                    break
                if line.strip() != '':
                    tlog.debug("%s: '%s'" % (tag, line))
                    try:
                        packet = json.loads(line)
                        Emitter.send(packet['event'], packet['message'])
                    except Exception as exc:
                        tlog.info("%s: BAD LINE '%s'\n%s" % (tag, line, traceback.format_exc()))
                        Emitter.note(line)
                        pass
                    pass
                pass
            if self.process.returncode is not 0:
                Emitter.note("Restore failed with error code %d" % self.process.returncode)
                pass
            pass
        except:
            pass
        if devname:
            Emitter.send(tag, {"device": ''})
        pass

    def is_running(self):
        # FIXME: this needs to be more accuarte.
        return self.process and self.process.returncode is None

    def terminate(self):
        if not self.is_running():
            return
        # FIXME: this would certainly kill the thread
        process = self.process
        self.process = None
        process.terminate()
        pass


    pass
