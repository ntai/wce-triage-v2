
export type ItemType = {
    label: string;
    value: string;
}

// This comes from the backend
export type DiskImageType = {
    mtime: string; // timestamp
    restoreType: string; // "wce-20", etc.
    name: string;
    fullpath: string;
    size: number;
    subdir: string;
    index: number;
}


export type DiskType = {
    target: number;
    deviceName: string;
    runTime: number;
    runEstimate: number;
    mounted: boolean;
    size: number;
    bus: "usb" | "ata";
    model: string;
    vendor: string;
    serial_no: string;
    smart: string;
    smart_enabled: boolean;
    wipe?: string;
    progress?: number;
    runMessage?: string;
}

export type TaskStatusType = "waiting" | "running" | "done" | "fail";

export type TaskInfo = {
    step: "" | number;
    taskCategory: string;
    taskProgress: number;
    taskEstimate: number;
    taskElapse: number;
    taskStatus: TaskStatusType;
    taskMessage: null | string;
    taskExplain: string;
    taskVerdict?: string[];
}

export type RunStatusType = "Waiting" | "Prepare" | "Preflight" | "Running" | "Success" | "Failed";

// FIXME: This is a terrible design.
export type RunReportType = {
    report: "tasks" | "task_progress" | "task_failure" | "task_success" | "run_progress";
    device: string;
    runStatus: RunStatusType;
    runMessage: string;
    runEstimate: number;
    runTime: number;
    step?: number;
    task?: TaskInfo;
    tasks?: TaskInfo[];
    _sequence_: number;
}

export type FanOutCopyRunState = {
    key: string; // device name
    totalBytes: number; // bytesCopied,
    destination: string; // dest_path,
    runStatus: RunStatusType;
    runMessage: string;
    progress: string;
    remainingBytes: number;
    runEstimate : number;
}

// "wipe-types.js"
export type WipeType = {
    id: string;
    name: string;
    arg: string;
}

export type DeviceSelectionType<T> = { [deviceName: string]: T };

// .disk_image_type.json format
export type ImageMetaType = {
    id: string; // restoreType on source type
    filestem: string;
    name: string;
    media?: string;
    timestamp: boolean;
    efi_image?: string;
    wce_share_url?: string;
    partition_map: string; // gpt, mbr
    randomize_hostname: boolean;
    cmdline: object;
    index: number;
}

export type CPUInfoType = {
    benchmarks?: {
        [benchmark_name: string]: { baseline: number, score: number }
    };
    machine?: string;
    board?: string;
    name: string;
    description: string;
    config: string;
    memory_size?: string;
    n_processors?: number;
    n_physical_cores?: number;
    n_logical_cores?: number;
    rating: string;
}

export type ComponentTriageType = {
    component: string;
    device?: string;
    device_type?: string;
    message?: string;
    result: boolean;
}

export type TriageResultType = {
    components: ComponentTriageType[];
}

export type TriageUpdateType = {
    component: string;
    device: string;
    result: boolean;
    message: string;
}