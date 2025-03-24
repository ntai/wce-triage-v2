import asyncio
import threading
import queue
import socketio


class EmitterThread(threading.Thread):
    """Bridge between the therad and socketio world"""

    def __init__(self, emit_queue: queue.Queue, sockio: socketio.AsyncServer):
        self.emit_queue = emit_queue
        self.sockio = sockio
        super().__init__(name="EmitterThread")

    def run(self):
        # Create a new event loop for the thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Define the async function to be called
        async def sock_emit():
            while True:
                event, message = self.emit_queue.get()
                await self.sockio.emit(event, message)

        # Run the async function in the event loop
        loop.run_until_complete(sock_emit())
        loop.close()


def start_emitter_thread(sockio: socketio.AsyncServer) -> queue.SimpleQueue:
    emit_queue = queue.SimpleQueue()
    emitter = EmitterThread(emit_queue, sockio)
    emitter.start()
    return emit_queue
