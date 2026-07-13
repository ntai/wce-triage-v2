#
# Typed payloads for the socket.io events pushed to the web client
# (see TriageServer.send_to_ui / EmitterThread in api/emitter.py).
#
from typing import List, Optional

from pydantic import BaseModel

from .formatters import DiskInfo


class ComponentDecision(BaseModel):
  """One entry in Computer.decisions - the triage verdict for a single
  component, or the synthetic 'Overall' aggregate entry (which carries only
  component/result - no message/device/verdict)."""
  component: str
  result: bool
  message: Optional[str] = None
  device: Optional[str] = None
  verdict: Optional[List[str]] = None
  pass


class TriageUpdateEvent(BaseModel):
  """Payload for the 'triageupdate' socket event, and the GET /triage response
  (same underlying server._triage model). TriageServer.send_to_ui() adds a
  top-level `_sequence_` key once this is dispatched - the same mechanism the
  disks/loadimage/saveimage/zerowipe/diskimage events rely on - so the model
  intentionally doesn't declare that field itself."""
  components: List[ComponentDecision]
  pass


class DisksEvent(BaseModel):
  """Payload for the 'disks' socket event (TriageServer.update_triage() ->
  DiskModel). Same _sequence_ convention as TriageUpdateEvent."""
  disks: List[DiskInfo]
  pass


class LogMessageEvent(BaseModel):
  """Payload for the 'message' socket event (UserMessages/ErrorMessages via
  MessageSocketIOView). severity is 1 (note) or 2 (error)."""
  message: str
  severity: int
  pass
