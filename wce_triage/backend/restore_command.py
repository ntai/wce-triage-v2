from .threaded_command import ThreadedCommandRunner
from .emitter import Emitter

#
class RestoreCommandRunner(ThreadedCommandRunner):

    def __init__(self, end_func, *args):
        super().__init__("restore", end_func, *args)
        pass

    def ending(self):
        Emitter.send(self.tag, {"device": ''})
        super().ending()
        pass

    pass
