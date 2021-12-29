import threading
import queue
from ..lib.util import get_triage_logger
from flask_socketio import emit, SocketIO

tlog = get_triage_logger()

#
# WebSocket sender.
#
# is a FIFO queue. You put in a message you want to send using _send().
# http server polls the out side of queue, and send out a packet to
# the listener.
#
# What's in the queue?
# The element is 3-item length tuple.
# 1: the sequence number of element.
# 2: WebSocket's event
# 3: WebSocket's data
#
# The event name here and UI side websocket need to match or else the
# message is ignored.
# FIXME: Have some kind of dictionary between the front/back ends.
#
# Known event type: message, diskupdate, triageupdate, loadimage, saveimage
#

class Emitter(threading.Thread):
    queue = None
    item_count = 0
    me = None

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.me = self
        self.queue = queue.SimpleQueue()
        self.start()
        pass

    # noinspection PyMethodParameters
    def run(self):
        try:
            while True:
                self.read_event()
                pass
        except queue.Empty:
            pass
        pass

    def read_event(self):
        elem = self.queue.get(block=True)
        tlog.debug("EMITTER: sending %d: '%s' '%s'" % (elem[0], elem[1], elem[2]))
        message = elem[2]
        message['_sequence_'] = elem[0]
        emit(elem[1], message)
        self.owner.peek_message(elem[1], message)
        pass

    # noinspection PyMethodParameters
    @classmethod
    def send(self, event, data):
        tlog.debug("EMITTER: queueing %d  %s" % (Emitter.item_count, event))
        Emitter.queue.put((Emitter.item_count, event, data))
        Emitter.item_count += 1
        pass

    # This is to send message
    # noinspection PyMethodParameters
    @classmethod
    def note(self, message):
        Emitter.send('message', {"message": message, "severity": 1})
        pass

    # This is to send alert message (aka popping up a dialog
    # noinspection PyMethodParameters
    @classmethod
    def alert(self, message):
        tlog.info("ALERT: " + message)
        Emitter.send('message', {"message": message, "severity": 2})
        pass

    pass


def init_socketio(socketio: SocketIO):
    @socketio.on('connect')
    def connect(auth):
        wockid = "foo"
        #me.channels[wockid] = environ
        tlog.debug("WOCK: %s connected" % wockid)
        return None

    @socketio.on('message')
    async def message(data):
        wockid = "foo"
        tlog.debug("WOCK: %s incoming %s" % (wockid, data))
        return None

    @socketio.on('disconnect')
    def disconnect():
        wockid = "foo"
        tlog.debug("WOCK: %s disconnect" % (wockid))
        return None

    pass
