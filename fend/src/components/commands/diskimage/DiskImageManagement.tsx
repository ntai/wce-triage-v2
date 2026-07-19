import React from 'react';
import {makeStyles, withStyles} from '@mui/styles';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import DiskImageTreeView, {DiskImageOperationType} from "./DiskImageTreeView";
import Grid from "@mui/material/Grid";
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import Disks, {DeviceSelectionType, DiskType} from "../../parts/Disks";
import {socket} from "../../common/socket";
import {RunnerStatus} from "../../../types/socket-events";
import {sweetHome} from "../../../looseend/home";
import Button from "@mui/material/Button";
import BuildIcon from '@mui/icons-material/Build';
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import Menu, {MenuProps} from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemText from '@mui/material/ListItemText';
import RunnerProgress from "../../parts/RunnerProgress";
import Tooltip from '@mui/material/Tooltip';
import CancelIcon from '@mui/icons-material/Cancel';
import {isProcessRunning} from "../../common/backend";


const appbarStyles = makeStyles( theme => ({
  root: {
    height: 46,
    minHeight: 46,
  },
  colorSecondary: {
    backgroundColor: '#208040'
  },
  commandButton: {
    marginRight: theme.spacing(2),
  },
}));


const StyledMenu = withStyles({
  paper: {
    border: '1px solid #d3d4d5',
  },
})((props:MenuProps) => (
  <Menu
    elevation={0}
    anchorOrigin={{
      vertical: 'bottom',
      horizontal: 'center',
    }}
    transformOrigin={{
      vertical: 'top',
      horizontal: 'center',
    }}
    {...props}
  />
));

const StyledMenuItem = withStyles(theme => ({
  root: {
    '&:focus': {
      backgroundColor: theme.palette.common.white,
      '& .MuiListItemIcon-root, & .MuiListItemText-primary': {
        color: theme.palette.common.black,
      },
    },
  },
}))(MenuItem);

interface OpMenuProps {
  expandAllCatsCB: (sel: boolean) => void;
  selectAllFilesCB: (all: boolean) => void;
}

function OpMenu({ expandAllCatsCB, selectAllFilesCB} : OpMenuProps) {
  const myAppbar = appbarStyles();
  const [anchorEl, setAnchorEl] = React.useState<EventTarget & HTMLButtonElement|null>(null);

  function handleClick(event: React.MouseEvent<HTMLButtonElement>) {
    const currentTarget = event.currentTarget;
    if (event?.currentTarget)
      setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const allCagetories = (select: boolean) => {
    setAnchorEl(null);
    expandAllCatsCB(select);
  };

  const handleCollapseCategories = () => {
    allCagetories(false);
  };

  const handleExpandCategories = () => {
    allCagetories(true);
  };

  const selectAllFiles = (select: boolean) => {
    setAnchorEl(null);
    selectAllFilesCB(select);
  };

  const deselectAll = () => {
    selectAllFiles(false);
  };

  const selectAll = () => {
    selectAllFiles(true);
  };

  return (
    <div>
      <IconButton
        edge="start" className={myAppbar.commandButton} color="inherit"
        aria-label="menu"
        aria-controls="customized-menu"
        aria-haspopup="true"
        onClick={handleClick}>
        <MenuIcon/>
      </IconButton>

      <StyledMenu
        id="customized-menu"
        anchorEl={anchorEl}
        keepMounted
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <StyledMenuItem onClick={handleExpandCategories}>
          <ListItemText primary="Expand all categories" />
        </StyledMenuItem>
        <StyledMenuItem onClick={handleCollapseCategories}>
          <ListItemText primary="Collapse all categories" />
        </StyledMenuItem>
        <StyledMenuItem onClick={selectAll}>
          <ListItemText primary="Select all" />
        </StyledMenuItem>
        <StyledMenuItem onClick={deselectAll}>
          <ListItemText primary="Deselect all" />
        </StyledMenuItem>
      </StyledMenu>
    </div>
  );
}

interface DiskImageMenubarProps {
  syncImages: () => void;
  deleteImages: () => void;
  abortSync: () => void;
  syncImageEnabled: boolean;
  deleteImageEnabled: boolean;
  syncRunning: boolean;
}


function DiskImageMenubar(props : DiskImageMenubarProps & OpMenuProps) {
  const myAppbar = appbarStyles();
  const {syncImages, deleteImages, abortSync, syncImageEnabled, deleteImageEnabled, syncRunning} = props;

  return (
    <AppBar classes={{root: myAppbar.root, colorSecondary: myAppbar.colorSecondary}} position="static"
            color={"secondary"}>
      <Toolbar variant="dense">
        <OpMenu {...props} />
        <Tooltip title="Sync disk images to disk">
          <Button aria-label="sync" disabled={!syncImageEnabled} startIcon={<BuildIcon />} className={myAppbar.commandButton} color="inherit" onClick={() => syncImages()} >Sync Images</Button>
        </Tooltip>
        <Tooltip title="Delete disk images from disk">
          <Button aria-label="delete" startIcon={<DeleteForeverIcon />} className={myAppbar.commandButton} color="inherit" onClick={() => deleteImages()} disabled={!deleteImageEnabled}>Delete Images</Button>
        </Tooltip>
        <Tooltip title="Abort sync/clean in progress">
          <Button aria-label="abort" startIcon={<CancelIcon />} className={myAppbar.commandButton} color="inherit" onClick={() => abortSync()} disabled={!syncRunning}>Abort</Button>
        </Tooltip>
      </Toolbar>
    </AppBar>
  )
}

type DiskImageManagementStateType = {
  /* Disk Image file selection - key is the image file */
  imageFileSelection: DeviceSelectionType<boolean>;

  /* target disks */
  targetDisks: DeviceSelectionType<DiskType>;

  runningStatus?: RunnerStatus;

  resetting: boolean;

  menuCommand?: DiskImageOperationType;
};


export default class DiskImageManagement extends React.Component<any, DiskImageManagementStateType> {
  constructor(props: any) {
    super(props);
    this.state = {
      /* Disk Image file selection */
      imageFileSelection: {},

      /* target disks */
      targetDisks: {},

      runningStatus: undefined,

      resetting: false,
    };

    this.did_reset = this.did_reset.bind(this);
    this.onRunnerUpdate = this.onRunnerUpdate.bind(this);
  }

  imageFileSelection(selectedImages: DeviceSelectionType<boolean>) {
    this.setState( { imageFileSelection: selectedImages });
  }

  diskSelectionChanged(selectedDisks: DeviceSelectionType<DiskType>, clicked?: DiskType) {
    if (!clicked) {
      this.setState({targetDisks: selectedDisks});
      return;
    }
    let targetDisks = Object.assign({}, this.state.targetDisks);

    if (targetDisks[clicked.deviceName]) {
      delete targetDisks[clicked.deviceName];
    } else {
      if (!clicked.mounted)
        targetDisks[clicked.deviceName] = clicked;
    }
    this.setState({targetDisks});
  }

  expandCats(expand: boolean) { this.setState( {menuCommand: expand ? "expand" : "collapse"}) }
  selectAll(select: boolean) {this.setState( {menuCommand: select ? "selectall" : "deselectall"})}

  clearCommand() {
    this.setState( {menuCommand: undefined} );
  }

  did_reset() {this.setState({resetting: false});}

  componentDidMount() {
    this.fetchSyncStatus();
    socket.on("diskimage", this.onRunnerUpdate);
  }

  componentWillUnmount() {
    socket.off("diskimage", this.onRunnerUpdate);
  }

  fetchSyncStatus() {
    fetch(sweetHome.backendUrl + "/dispatch/sync/status").then(res => {
      res.json().then(status => this.onRunnerUpdate(status));
    });
  }

  getSyncImageUrl() {
    // Make array rather than json object.
    const targetDiskList = Object.keys(this.state.targetDisks).filter( devName => this.state.targetDisks[devName]);
    const imageFiles = Object.keys(this.state.imageFileSelection).filter( filename => this.state.imageFileSelection[filename]);

    if (targetDiskList.length === 0 || imageFiles.length === 0) {
      return undefined;
    }

    // time to make donuts
    console.log(targetDiskList);

    let url = sweetHome.backendUrl + "/dispatch/sync?deviceNames=";
    let sep = "";
    var targetDisk;
    for (targetDisk of targetDiskList) {
      url = url + sep + targetDisk;
      sep = ",";
    }
    url = url + "&sources=";
    let imageFile;
    let imageFileList = "";
    sep = "";
    for (imageFile of imageFiles) {
      url = url + sep + imageFile;
      sep = ",";
    }
    return url;
  }

  getDeleteImageUrl() {
    // Make array rather than json object.
    const targetDiskList = Object.keys(this.state.targetDisks).filter( devName => this.state.targetDisks[devName]);

    if (targetDiskList.length === 0) {
      return undefined;
    }

    var url = sweetHome.backendUrl + "/dispatch/clean?deviceNames=";
    var sep = "";
    var targetDisk;
    for (targetDisk of targetDiskList) {
      url = url + sep + targetDisk;
      sep = ",";
    }
    return url;
  }


  syncImages() {
    const url = this.getSyncImageUrl();
    console.log(url);
    if (url) {
      console.log(url);
      fetch(url, {"method":"POST"}).then(_ => {
        this.fetchSyncStatus();
      });
    }
  }

  deleteImages() {
    const url = this.getDeleteImageUrl();
    console.log(url);
    if (url) {
      console.log(url);
      fetch(url, {"method":"POST"}).then(_ => {
        this.fetchSyncStatus();
      });
    }
  }

  abortSync() {
    fetch(sweetHome.backendUrl + "/dispatch/sync/stop", {"method":"POST"}).then(_ => {
      this.fetchSyncStatus();
    });
  }

  onRunnerUpdate(update: RunnerStatus) {this.setState({runningStatus: update});}

  onReset() {
    this.setState({
      resetting: true,
      targetDisks: {}
    });
    // this.fetchSources();
    // this.setState( {wipeOption: undefined})
  }

  render() {
    const {resetting, runningStatus, targetDisks} = this.state;
    const syncImageEnabled = this.getSyncImageUrl() !== undefined;
    const deleteImageEnabled = this.getDeleteImageUrl() !== undefined;
    const isRunning = isProcessRunning(runningStatus?.runStatus);

    return (
      <div style={{ padding: 0 }}>
        <Grid container spacing={1}>
          <Grid container size={12}>
            <DiskImageMenubar syncImageEnabled={syncImageEnabled}
                              deleteImageEnabled={deleteImageEnabled}
                              syncRunning={isRunning}
                              syncImages={this.syncImages.bind(this)}
                              deleteImages={this.deleteImages.bind(this)}
                              abortSync={this.abortSync.bind(this)}
                              expandAllCatsCB={this.expandCats.bind(this)}
                              selectAllFilesCB={this.selectAll.bind(this)} />
          </Grid>
          <Grid size={4}>
            <Box sx={{border: 2, borderColor: "grey.500", borderRadius: 4}}>
              <Typography>Disk Images</Typography>
              <DiskImageTreeView selectionChangedCB={this.imageFileSelection.bind(this)}
                                 command={this.state.menuCommand}
                                 clearCommand={this.clearCommand.bind(this)}/>
            </Box>
          </Grid>
          <Grid size={8}>
            <Box sx={{border: 2, borderColor: "grey.500", borderRadius: 4}}>
              <Typography>Destination Disks</Typography>
              <Disks maxSelected={100} running={isRunning} selected={targetDisks} runningStatus={runningStatus} resetting={resetting}
                     did_reset={this.did_reset.bind(this)} diskSelectionChanged={this.diskSelectionChanged.bind(this)}/>
            </Box>
          </Grid>
        </Grid>
        <Grid size={12}>
          <RunnerProgress runningStatus={runningStatus} statuspath={"/dispatch/sync/status"}  />
        </Grid>
      </div>
    );
  };
}
