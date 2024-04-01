#
# messages is like a logging but it's for the user from the triage.
#

from .models import Model, ModelDispatch

class MessagesModel(Model):
  def __init__(self):
    super().__init__(cumulative=True)
    pass

class MessageDispatch(ModelDispatch):
  def note(self, message):
    return self.dispatch({"message": message, "severity": 1})

  def error(self, message):
    return self.dispatch({"message": message, "severity": 2})


class ErrorDispatch(ModelDispatch):
  def dispatch(self, update):
    return super().dispatch({"message": update, "severity": 2})
  pass


message_model = MessagesModel()
UserMessages = MessageDispatch(message_model)
ErrorMessages = ErrorDispatch(message_model)

async def main():
  from .view import ConsoleView
  view = ConsoleView()
  UserMessages.set_view(view)

  tag = "test"
  context = {}
  UserMessages.start(tag, context)

  UserMessages.note("hello\n")
  UserMessages.error("kitty\n")

  UserMessages.end(tag, context)
  print(UserMessages.model.data)


if __name__ == "__main__":
  import asyncio
  asyncio.run(main())
