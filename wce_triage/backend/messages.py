#
# messages is like a logging but it's for the user from the triage.
#

from .models import StringsModel, StringsDispatch

class MessagesModel(StringsModel):
  def __init__(self):
    super().__init__()
    self._model = {"message": []}
    pass

  def append_line(self, message):
    self._model["message"].append(message)
    pass

class MessageDispatch(StringsDispatch):
  def note(self, message):
    self.dispatch(message)
    pass

  def error(self, message):
    self.dispatch(message)
    pass

UserMessages = MessageDispatch(MessagesModel())
