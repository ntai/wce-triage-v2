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
