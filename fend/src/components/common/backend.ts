import {RunStatusType} from "./types";

export function isProcessRunning(status?: RunStatusType) : boolean {
  return status === "Waiting" || status === "Prepare" || status === "Preflight" || status === "Running";
}
