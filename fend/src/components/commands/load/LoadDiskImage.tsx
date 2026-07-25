import React from "react";
import {sweetHome} from '../../../looseend/home';
import {socket} from "../../common/socket";
import {RunnerStatus} from "../../../types/socket-events";
import RunnerProgress from "../../parts/RunnerProgress";
import Disks, {DeviceSelectionType, DiskType} from "../../parts/Disks";
import Catalog from "../../parts/Catalog";
import WipeOption, {ItemType} from "../../parts/WipeOption";
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import DiskImageSelector, {SourceType, ToDiskSources} from '../diskimage/DiskImageSelector';
import "../commands.css";
import BuildIcon from '@mui/icons-material/Build';
import RefreshIcon from "@mui/icons-material/Refresh";
import CancelIcon from "@mui/icons-material/Cancel";
import {isProcessRunning} from "../../common/backend";


type LoadDiskImageStateType = {
  /* The disk images sources */
  sources: SourceType[];
  /* The disk images sources */
  subsetSources: SourceType[];
  /* Selected disk image source. Because the selection can be multiple by original implementation, the value her is always a single elemnt array. */
  source: SourceType|undefined;
  /* Fetching the disk images */
  sourcesLoading: boolean;

  /* wipe */
  wipeOptions: ItemType[];
  wipeOption?: ItemType;

  /* The restore types */
  restoreTypes: ItemType[];
  restoreType?: string;

  /* target disks */
  targetDisks: DeviceSelectionType<DiskType>;

  runningStatus?: RunnerStatus;

  resetting : boolean;
};


export default class LoadDiskImage extends React.Component<any,LoadDiskImageStateType> {

  constructor(props:any) {
    super(props);
    this.state = {
      /* The disk images sources */
      sources: [],
      /* The disk images sources */
      subsetSources: [],
      /* Selected disk image source. Because the selection can be multiple by original implementation, the value her is always a single elemnt array. */
      source: undefined,
      /* Fetching the disk images */
      sourcesLoading: true,

      /* wipe */
      wipeOptions: [],
      wipeOption: undefined,


      /* The restore types */
      restoreTypes: [],
      restoreType: '',

      /* target disks */
      targetDisks: {},

      runningStatus: undefined,

      resetting : false
    };

    this.fetchSources = this.fetchSources.bind(this);
    this.setRestoreType = this.setRestoreType.bind(this);
    this.setRestoreTypes = this.setRestoreTypes.bind(this);
    this.did_reset = this.did_reset.bind(this);
    this.onRunnerUpdate = this.onRunnerUpdate.bind(this);
  }

  // FIXME: clicked needs a real type here.
  diskSelectionChanged(selectedDisks: DeviceSelectionType<DiskType>, clicked?: DiskType) {
    if (!clicked) {
      this.setState({targetDisks: selectedDisks});
      return;
    }
    let newSelection = Object.assign( {}, this.state.targetDisks);

    if (this.state.targetDisks[clicked.deviceName]) {
        delete newSelection[clicked.deviceName];
    }
    else {
      if (!clicked.mounted)
        newSelection[clicked.deviceName] = clicked;
    }
    this.setState( {targetDisks: newSelection});
  }

  did_reset() {
    this.setState( {resetting: false});
  }


  onReset() {
    this.setState( {
      resetting: true,
      source: undefined,
      sources: [],
      subsetSources: [],
      targetDisks: {}
    });
    this.fetchSources();
    // this.setState( {wipeOption: undefined})
  }

  setSource(source?: SourceType) {
    const restoreType = this.state.restoreTypes.find(rt => rt.value === source?.restoreType);
    this.setState({source: source, restoreType: restoreType?.value});
    console.log("Restore type:" + JSON.stringify(restoreType));
    this.forceUpdate();
  }

  selectWipe(selected?: ItemType) {
    this.setState({wipeOption: selected})
  }

  setWipeOptions(wipers: ItemType[]) {
    this.setState({wipeOptions: wipers, wipeOption: wipers[0]})
  }

  setRestoreType(restoreTypeID?: string) {
    if (restoreTypeID === undefined)
      return;
    console.log("selected restoreType: " + restoreTypeID);

    var subset : SourceType[] = [];
    if (this.state.sources) {
      subset = this.state.sources.filter(source => source.restoreType === restoreTypeID);
      if (subset.length > 1) {
        subset.sort((a, b) => Date.parse(b.mtime) - Date.parse(a.mtime));
      }
    }

    var source = undefined;

    if (subset.length > 0) {
      source = subset[0];
    }
    this.setState({restoreType: restoreTypeID, subsetSources: subset, source: source})
  }

  setRestoreTypes(catalog: ItemType[]) {
    console.log("LoadDiskImage::setRestoreTypes");
    console.log(catalog);
    this.setState({restoreTypes: catalog, restoreType: undefined})
  }

  componentDidMount() {
    this.fetchSources();
    this.fetchDiskLoadStatus();
    socket.on("loadimage", this.onRunnerUpdate);
  }

  componentWillUnmount() {
    socket.off("loadimage", this.onRunnerUpdate);
  }

  onRunnerUpdate(update: RunnerStatus) {
    this.setState({runningStatus: update});
  }

  fetchDiskLoadStatus() {
    fetch(sweetHome.backendUrl + "/dispatch/load/status").then(res => {
      res.json().then(status => this.onRunnerUpdate(status));
    });
  }

  getRestoringUrl() {
    // Make array rather than json object.
    const targetDiskList = Object.keys(this.state.targetDisks).filter( devName => this.state.targetDisks[devName]);
    const resotringSource = this.state.source;
    const restoreType = this.state.restoreType;

    if (targetDiskList.length === 0 || !resotringSource || !restoreType) {
      return undefined;
    }

    // time to make donuts
    var wipe = "";
    if (this.state.wipeOption !== undefined) {
      wipe = "&wipe=" + this.state.wipeOption.value;
      console.log(this.state.wipeOption)
    }

    console.log(targetDiskList);

    if (targetDiskList.length > 1) {
      var url = sweetHome.backendUrl + "/dispatch/load?deviceNames=";
      var sep = "";
      var targetDisk;
      for (targetDisk of targetDiskList) {
        url = url + sep + targetDisk;
        sep = ",";
      }
      url = url + "&source=" + resotringSource.value + "&size=" + resotringSource.filesize + "&restoretype=" + restoreType + wipe;
      return encodeURI(url);
    }
    else {
      const targetDisk = targetDiskList[0];
      return encodeURI(sweetHome.backendUrl + "/dispatch/load?deviceNames=" + targetDisk + "&source=" + resotringSource.value + "&size=" + resotringSource.filesize + "&restoretype=" + restoreType + wipe);
    }
  }

  onLoad() {
    const restoringUrl = this.getRestoringUrl();
    if (restoringUrl === undefined) {
      console.log("Cannot load as there is no valid restoring url");
      return;
    }
    console.log(restoringUrl);

    // time to make donuts
    // const selectedDevices = Object.keys(this.state.targetDisks).filter( devName => this.state.targetDisks[devName]);
    // const targetDisk = selectedDevices[0];
    // var remainings = {}
    // Object.keys(this.state.targetDisks).slice(1).map( tag => remainings[tag] = true )
    // this.setState({ targetDisks: remainings, target: targetDisk });

    fetch(restoringUrl, { "method":"POST" })
        .then(_ => {
          this.fetchDiskLoadStatus();
        });
  }

  onAbort() {
    fetch(sweetHome.backendUrl + "/dispatch/load/stop", {
      "method":"POST"})
      .then(_ => {
        this.fetchDiskLoadStatus();
      });
  }


  fetchSources() {
    this.setState({ sourcesLoading: true });
    // Request the data however you want.  Here, we'll use our mocked service we created earlier

    fetch(sweetHome.backendUrl + "/dispatch/disk-images").then(reply => reply.json()).then(res => {
      const srcs = ToDiskSources(res.sources as any);
      let src = undefined;
      let restoreType: string|undefined = undefined;
      // if there is only one image source, pick it.
      if (srcs.length === 1) {
        src = srcs[0];
        restoreType = src.restoreType;
      }
      // Now just get the rows of disks to your React Table (and update anything else like total pages or loading)
      this.setState({
        sources: srcs,
        subsetSources: srcs,
        source: src,
        restoreType: restoreType
      });
    }).finally( () => { this.setState( {sourcesLoading: false}); });
  }

  render() {
    const { subsetSources, source, wipeOption, restoreType, resetting, runningStatus, targetDisks } = this.state;
    const restoringUrl = this.getRestoringUrl();
    const diskRestoring = isProcessRunning(runningStatus?.runStatus);

    return (
        <React.Fragment>
          <Box sx={{ display: 'flex', flexWrap: 'wrap' }}>
            <Box sx={{ width: '16.6667%' }}>
              <Catalog title={"Restore type"}
                       catalogType={restoreType}
                       catalogTypeChanged={this.setRestoreType}
                       catalogTypesChanged={this.setRestoreTypes}/>
            </Box>

            <Box sx={{ width: '33.3333%' }}>
              <DiskImageSelector setSource={this.setSource.bind(this)}
                                 sources={subsetSources} source={source}/>
            </Box>

            <Box sx={{ width: '16.6667%' }}>
              <WipeOption title={"Wipe"} wipeOption={wipeOption}
                          wipeOptionChanged={this.selectWipe.bind(this)}
                          wipeOptionsChanged={this.setWipeOptions.bind(this)}/>
            </Box>

            <Box sx={{ width: '8.3333%' }}>
              <Button startIcon={<BuildIcon/>} variant="contained" color="secondary"
                      onClick={() => this.onLoad()} disabled={restoringUrl === undefined}>Load</Button>
            </Box>

            <Box sx={{ width: '16.6667%' }}>
              <ButtonGroup>
                <Button startIcon={<RefreshIcon/>} size="small" variant="contained" color="primary"
                        onClick={() => this.onReset()}>Reset</Button>
                <Button startIcon={<CancelIcon/>} size="small" variant="contained" color="secondary"
                        onClick={() => this.onAbort()} disabled={!diskRestoring}>Abort</Button>
              </ButtonGroup>
            </Box>
            <Box sx={{ width: '100%' }}>
              <Disks maxSelected={100} running={diskRestoring} selected={targetDisks}
                     runningStatus={runningStatus} resetting={resetting} did_reset={this.did_reset}
                     diskSelectionChanged={this.diskSelectionChanged.bind(this)}/>
            </Box>
            <Box sx={{ width: '100%' }}>
              <RunnerProgress runningStatus={runningStatus} statuspath={"/dispatch/load/status"}/>
            </Box>
          </Box>
        </React.Fragment>
    );
  }
}

