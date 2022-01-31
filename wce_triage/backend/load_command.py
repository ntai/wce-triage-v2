from .process_runner import ProcessRunner
from .models import MessageDispatch
from
#
class RestoreCommandRunner(ProcessRunner):

    def __init__(self, end_func, *args):
        super().__init__("restore", end_func, *args)
        pass



    def ending(self):
        # Emitter.send(self.tag, {"device": ''})
        super().ending()
        pass

    pass
