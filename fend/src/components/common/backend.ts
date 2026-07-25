import {RunState} from "../../types/api-types";

export function isProcessRunning(status?: RunState) : boolean {
  return status === "Waiting" || status === "Prepare" || status === "Preflight" || status === "Running";
}
