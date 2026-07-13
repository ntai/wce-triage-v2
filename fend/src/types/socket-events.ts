import { components } from "./triage-api";

// TriageServer.send_to_ui() (wce_triage/api/server.py) splices a top-level
// `_sequence_` into every dict-shaped payload outside the pydantic model itself -
// see the TriageUpdateEvent docstring in wce_triage/api/socket_protocol.py.
type Sequenced<T> = T & { _sequence_: number };

// Re-exported for components that also consume the REST status endpoints
// (e.g. /dispatch/wipe/status), which return a plain OperationProgress with
// no _sequence_ - unlike the socket event, which is Sequenced<OperationProgress>.
export type OperationProgress = components["schemas"]["OperationProgress"];
export type TaskStatus = components["schemas"]["TaskStatus"];

// The load/save/wipe/sync status components feed their `runningStatus` state from
// two origins: an initial REST fetch (plain OperationProgress, no _sequence_) and
// the matching socket event (Sequenced<OperationProgress>). _sequence_ is optional
// here to cover both.
export type RunnerStatus = OperationProgress & { _sequence_?: number };

// Event name -> payload type, matching EmitterThread's sockio.emit(event, message)
// (wce_triage/api/emitter.py). unmount/opticaldrive are declared server-side but
// never actually emitted today, and networksettings is listened for in
// NetworkSettings.js with no backend emitter at all - omitted here rather than
// typed against a shape nothing sends.
export type SocketEventMap = {
  disks: Sequenced<components["schemas"]["DisksEvent"]>;
  loadimage: Sequenced<components["schemas"]["OperationProgress"]>;
  saveimage: Sequenced<components["schemas"]["OperationProgress"]>;
  zerowipe: Sequenced<components["schemas"]["OperationProgress"]>;
  diskimage: Sequenced<components["schemas"]["OperationProgress"]>;
  triageupdate: Sequenced<components["schemas"]["TriageUpdateEvent"]>;
  message: Sequenced<components["schemas"]["LogMessageEvent"]>;
};
