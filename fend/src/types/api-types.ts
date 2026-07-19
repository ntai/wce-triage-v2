import { components } from "./triage-api";

// Thin re-exports of generated schema types under the names components
// already use, mirroring the convention in socket-events.ts. Prefer these
// over reaching into components["schemas"][...] directly at call sites.

export type DiskInfo = components["schemas"]["DiskInfo"];
export type BusType = components["schemas"]["BusType"];
export type DiskImageInfo = components["schemas"]["DiskImageInfo"];
export type WipeType = components["schemas"]["WipeType"];
export type CpuInfo = components["schemas"]["CpuInfo"];
export type ComponentDecision = components["schemas"]["ComponentDecision"];
export type TriageUpdateEvent = components["schemas"]["TriageUpdateEvent"];
export type RunState = components["schemas"]["RunState"];

// The backend's "DiskImageType" schema describes a restore-type *catalog*
// entry (id/filestem/catalogDirectory/partition_plan/...) - unrelated to
// DiskImageInfo above (a listed local image *file*). Kept under this
// frontend-only name to avoid the collision when both are in scope.
export type ImageMetaType = components["schemas"]["DiskImageType"];