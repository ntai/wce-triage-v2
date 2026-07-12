import React from "react";
//
import {sweetHome} from '../../../looseend/home'

import Grid from '@mui/material/Grid';
import Button from '@mui/material/Button';
import { makeStyles } from '@mui/styles';

import PressPlay from "./PressPlay";
import {io} from "socket.io-client";
import Typography from '@mui/material/Typography';
import Mui5Table from '../../parts/Mui5Table';
import "../commands.css";
import CircularProgress from '@mui/material/CircularProgress';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import LoopIcon from '@mui/icons-material/Loop';
import StopIcon from '@mui/icons-material/Stop';
import Tooltip from "@mui/material/Tooltip";
import {ComponentTriageType, CPUInfoType, TriageResultType, TriageUpdateType} from "../../common/types";

// cssstyle 3.0.10 bug
const useStyles = makeStyles(theme => ({
  root: {
    padding: theme.spacing(0, 0),
    textAlign: 'left',
    rounded: true,
    fontSize: 11,
    width: '100%',
  },
  heading: {
    fontSize: theme.typography.pxToRem(15),
    fontWeight: "bold"
  },
}));


function CpuInfo(props: {
  onMount: (cpu_info: CPUInfoType) => void
}) {
  const [loading, setLoading] = React.useState(true);
  const [cpu_info, set_cpu_info] = React.useState<CPUInfoType>(
      {name: "Unknown", description: "", config: "", rating: "?"}
  );

  React.useEffect(() => {
    fetch(sweetHome.backendUrl + '/dispatch/cpu_info').then(rep => rep.json())
        .then(res => {
          const cpu_info: CPUInfoType = res.cpu_info as any;
          set_cpu_info(cpu_info);
          props.onMount(cpu_info);
        })
        .catch( err => {
          set_cpu_info({name: "Failed to communicate", description: err, config: "Unknown", rating: "?"});
        })
        .finally(() => setLoading(false));
  });

  if (loading) {
    return <CircularProgress/>
  }
  else {
    return (
      <Typography variant={"subtitle1"}>
        {cpu_info.name +  " " + cpu_info.description + " " + cpu_info.config}
      </Typography>
    )
  }
}


function CpuRating() {
  const classes = useStyles();
  const [cpu_info, set_cpu_info] = React.useState<CPUInfoType|undefined>(undefined);

  let summary = "CPU Rating: Expand to see. It may take a couple of minutes.";
  const mounted = (info: CPUInfoType) => (set_cpu_info(info));

  if (cpu_info) {
    summary = "CPU Rating: " + cpu_info.rating;
  }

  return (
    <div className={classes.root}>
      <Accordion slotProps={{ transition: { unmountOnExit: true } }}>
      <AccordionSummary
      expandIcon={<ExpandMoreIcon/>}
      aria-controls="panel1a-content"
      id="panel1a-header"
      >
        <Typography variant="body2">
          {summary}
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
         <CpuInfo onMount={mounted} />
      </AccordionDetails>

      </Accordion>
    </div>
  );
}


type TriageStateType = {
  triageResult: ComponentTriageType[];
  loading: boolean;
  show_cpu_info: boolean;
  cpu_info?: CPUInfoType;
  cpu_info_loading: boolean;
  soundPlaying: boolean;
  fontSize: number;
  opticals: ComponentTriageType[];
}

export default class Triage extends React.Component<any,TriageStateType> {
  constructor(props:any) {
    super(props);

    this.state = {
      triageResult: [],
      loading: true,
      show_cpu_info: false,
      cpu_info: undefined,
      cpu_info_loading: true,
      soundPlaying: false,
      fontSize: 14,
      opticals: []
    };

    this.fetchTriage = this.fetchTriage.bind(this);
  }

  fetchTriage() {
    this.setState({loading: true, triageResult: []});
    fetch(sweetHome.backendUrl + '/dispatch/triage').then(rep => rep.json()).then((res: TriageResultType) => {
      // Now just get the rows of triage results
      this.setState({
        triageResult: res.components,
        loading: false
      });
    });
  }

  componentDidMount() {
    const loadWock = io(sweetHome.websocketUrl);
    loadWock.on("triageupdate", this.onTriageUpdate.bind(this));
    this.fetchTriage();
  }

  setFontSize(fontSize:number) {
    this.setState({fontSize: fontSize});
  }


  onShutdown() {
    fetch(sweetHome.backendUrl + '/dispatch/shutdown?mode=poweroff', {"method": "POST"}).then( _ => {
      console.log("power off");
    });
  }


  onReboot() {
    fetch(sweetHome.backendUrl + '/dispatch/shutdown?mode=reboot', {"method": "POST"}).then(_ => {
      console.log("reboot");
    });
  }

  onMusicPlay() {
    let rows = JSON.parse(JSON.stringify(this.state.triageResult));
    let row;

    for (row of rows) {
      if (row.component === "Sound") {
        row.result = true;
        break;
      }
    }

    this.setState({triageResult: rows});
  }

  onOpticalTest() {
    fetch(sweetHome.backendUrl + '/dispatch/opticaldrive/test', {"method": "POST"}).then(_ => {
      console.log("optical drive test");
    });
  }

/*
  onBenchmark() {
    this.fetchCpuInfo();
    this.setState({show_cpu_info: true});
  }
 */

  onTriageUpdate(update:TriageUpdateType) {
    console.log(update);
    let rows: ComponentTriageType[] = JSON.parse(JSON.stringify(this.state.triageResult));
    let row;
    let updated;

    for (row of rows) {
      if (row.component === update.component) {
        if (row.device === update.device) {
          row.result = update.result;
          row.message = update.message;
          updated = row;
          break;
        }
      }
    }

    console.log(updated);

    this.setState({ triageResult: rows } );
  }

  render() {
    const data = this.state.triageResult;
    const fontSize = this.state.fontSize;

    return <div >
      <Grid container spacing={1}>

        <Grid size={1}>
            <Button startIcon={<RefreshIcon />} variant="contained" size="small" onClick={() => this.fetchTriage()}>
              Refresh
            </Button>
        </Grid>

        <Grid size={1}>
          <PressPlay tooltip={"Test sound"}  title={"\u266B"} kind={"mp3"}     onPlay={ () => this.onMusicPlay()} url={sweetHome.backendUrl + '/dispatch/music'}/>
        </Grid>
        <Grid size={1}>
          <PressPlay tooltip={"Test CD/DVD drive"} title={"\u25CE"} kind={"optical"} onPlay={ () => this.onOpticalTest()} url={sweetHome.backendUrl + '/dispatch/opticaldrive/test'}/>
        </Grid>

        <Grid size={2}>
          <Tooltip title={"Reboot computer"}>
            <Button startIcon={<LoopIcon />} variant="contained" size="small" color="secondary" onClick={ () => this.onReboot()}>
              Reboot
            </Button>
          </Tooltip>
          <Tooltip title={"Turn off computer"}>
            <Button startIcon={<StopIcon />} variant="contained" size="small" color="secondary" onClick={ () => this.onShutdown()} >
              Off
            </Button>
          </Tooltip>
        </Grid>

        <Grid size={2}>
          <Button variant="outlined" size="small" onClick={() => this.setFontSize(fontSize+2)}>
            {'Font \u25b3'}
          </Button>
          <Button variant="outlined" size="small" onClick={() => this.setFontSize(fontSize-2)}>
            {'Font \u25bd'}
          </Button>
        </Grid>

        <Grid size={5}>
          <CpuRating />
        </Grid>

        <Grid size={12}>
          <Mui5Table<ComponentTriageType>
            rows={data}
            isLoading={this.state.loading}
            style={{borderRadius: 0, borderWidth: 0, textAlign: "left", fontSize: this.state.fontSize, paddingTop: 5, paddingBottom: 5 }}
            options={{
              paging: false, sorting: false, draggable: false,
              toolbar: false, search: false, showTitle: false, detailPanelColumnAlignment: "left",
              rowStyle: { backgroundColor: "white", fontSize: this.state.fontSize, paddingTop: 3, paddingBottom: 3 },
            }}
            columns={[
              {
                title: "Component",
                render: row => row.component,
                cellStyle: { width: 100, textAlign: "right", fontSize: this.state.fontSize, paddingTop: 3, paddingBottom: 3 }
              },
              {
                title: "Result",
                cellStyle: { minWidth: 10 + this.state.fontSize * 5, textAlign: "left", fontSize: this.state.fontSize, paddingTop: 3, paddingBottom: 3 },
                render: row => (
                  // circle with color
                  <span>
                    <span style={{
                      color: row.result ? '#1fff2e' : '#ff2e00',
                      transition: 'all .3s ease'
                    }}>
                      {row.result ? '\u25cf' : '\u25a0' }
                    </span>
                    {row.result ? ' Pass' : ' Fail'}
                  </span>
                )
              },
              {
                title: "Details",
                render: row => row.message,
                cellStyle: { fontSize: this.state.fontSize, paddingTop: 3, paddingBottom: 3 }
              }
            ]} />
        </Grid>
      </Grid>
    </div>
  }
}
