import React from "react";
import {sweetHome} from '../../../looseend/home';
import {socket} from "../../common/socket";
import {RunnerStatus} from "../../../types/socket-events";
import RunnerProgress from "../../parts/RunnerProgress";
import Disks from "../../parts/Disks";
import Catalog from "../../parts/Catalog";
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import SaveIcon from '@mui/icons-material/Save';

import "../commands.css";
import RefreshIcon from "@mui/icons-material/Refresh";
import CancelIcon from "@mui/icons-material/Cancel";
import {ItemType, DiskType, DeviceSelectionType} from "../../common/types";
import {isProcessRunning} from "../../common/backend";


type SaveDiskImageStateType = {
  imageTypes: ItemType[];
  imageType?: string;

  sourceDisk?: string;
  runningStatus?: RunnerStatus;

  /* Selected disks */
  selectedDisks: DeviceSelectionType<DiskType>;

  resetting: boolean;
};


export default class SaveDiskImage extends React.Component<any,SaveDiskImageStateType> {
  constructor(props: any) {
    super(props);
    this.state = {
      /* Selected disk image destination. Because the selection can be multiple by original implementation, the value her is always a single element array. */
      imageTypes: [],
      imageType: undefined,

      sourceDisk: undefined,
      runningStatus: undefined,
      
      /* Selected disks */
      selectedDisks: {},

      resetting: false,
    };
    this.did_reset = this.did_reset.bind(this);
    this.setImageType = this.setImageType.bind(this);
    this.setImageTypes = this.setImageTypes.bind(this);
    this.onRunnerUpdate = this.onRunnerUpdate.bind(this);
  }

  componentDidMount() {
    this.fetchSavingStatus();
    socket.on("saveimage", this.onRunnerUpdate);
  }

  componentWillUnmount() {
    socket.off("saveimage", this.onRunnerUpdate);
  }

  onRunnerUpdate(update: RunnerStatus) {
    this.setState({runningStatus: update})
  }

  fetchSavingStatus() {
    fetch(sweetHome.backendUrl + "/dispatch/save/status").then(res => {
      res.json().then(status => this.onRunnerUpdate(status));
    });
  }

  setImageType(selected?: string) {
    console.log(selected);
    this.setState({imageType: selected})
  }

  setImageTypes(catalog: ItemType[]) {
    console.log(catalog);
    this.setState({imageTypes: catalog, imageType: undefined})
  }

  getImagingUrl() {
    const selectedDevices = Object.keys(this.state.selectedDisks).filter( devName => this.state.selectedDisks[devName]);
    const imagingType = this.state.imageType;

    if (selectedDevices.length === 0 || !imagingType) {
      return undefined;
    }

    // time to make donuts
    const sourceDisk = selectedDevices[0];
    return sweetHome.backendUrl + "/dispatch/save?deviceName=" + sourceDisk + "&type=" + imagingType;
  }

  onSave() {
    const savingUrl = this.getImagingUrl();
    console.log(savingUrl);
    if (savingUrl === undefined)
        return;

    fetch(savingUrl, {"method":"POST"}).then(_ => {
      this.fetchSavingStatus();
    });
  }

  onReset() {
    this.setState( {resetting: true, selectedDisks: {}});
    this.fetchSavingStatus();
  }

  diskSelectionChanged(selectedDisks: DeviceSelectionType<DiskType>, clicked?: DiskType) {
    if (!clicked) {
      this.setState({selectedDisks});
      return;
    }
    if (!clicked.mounted) {
      this.setState( {selectedDisks: {[clicked.deviceName]: clicked}});
    }
  }

  did_reset() {
    this.setState( {resetting: false});
  }

  onAbort() {
    fetch(sweetHome.backendUrl + "/dispatch/save/stop", {"method":"POST"}).then(res => {
      this.fetchSavingStatus();
    });
  }

  render() {
    const { runningStatus, resetting, selectedDisks } = this.state;
    const imagingUrl = this.getImagingUrl();
    const makingImage = isProcessRunning(runningStatus?.runStatus);

    return (
      <div>
        <Grid container>
          <Grid size={1}>
            <Button size="small" startIcon={<SaveIcon />} variant="contained" color="primary" onClick={() => this.onSave()} disabled={imagingUrl === undefined}>Save</Button>
          </Grid>

          <Grid size={5}>
            <Catalog title={"Disk image type"} catalogType={this.state.imageType} catalogTypeChanged={this.setImageType} catalogTypesChanged={this.setImageTypes}/>
          </Grid>

          <Grid size={1}>
            <Button startIcon={<RefreshIcon />} size="small" variant="contained" color="primary" onClick={() => this.onReset()}>Reset</Button>
          </Grid>
          <Grid size={1}>
            <Button startIcon={<CancelIcon />} size="small" variant="contained" color="secondary" onClick={() => this.onAbort()} disabled={!makingImage}>Abort</Button>
          </Grid>

          <Grid size={12}>
            <Disks running={makingImage} maxSelected={1} selected={selectedDisks} runningStatus={runningStatus} resetting={resetting} did_reset={this.did_reset} diskSelectionChanged={this.diskSelectionChanged.bind(this)} />
          </Grid>

          <Grid size={12}>
          <RunnerProgress runningStatus={runningStatus} statuspath={"/dispatch/save/status"}/>
          </Grid>

        </Grid>
      </div>
    );
  }
}
