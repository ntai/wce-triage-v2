import React from 'react';
import Triage from './commands/triage/Triage';
import LoadDiskImage from './commands/load/LoadDiskImage';
import SaveDiskImage from './commands/save/SaveDiskImage';
import Messages from './Messages';
import WipeDisk from "./commands/wipe/WipeDisk";
import TriageAppSettings from "./settings/TriageAppSettings";

import AppBar from '@mui/material/AppBar';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import DiskImageManagement from "./commands/diskimage/DiskImageManagement";


type TabPanelProps = {
  children?: React.ReactNode;
  value: number;
  index: number;
  visible?: boolean;
  title?: string;
};

class TabPanel extends React.Component<TabPanelProps> {
  render() {
    const {children, index, value} = this.props;
      return (
        <div>
          <Typography
            component="div"
            role="tabpanel"
            hidden={value !== index}
            id={`wrapped-tabpanel-${index}`}
            aria-labelledby={`wrapped-tab-${index}`}
          >
            <Box sx={{p: 1}}>{children}</Box>
          </Typography>
        </div>
      );
  }
}


function a11yProps(index: number) {
  return {
    id: `wrapped-tab-${index}`,
    'aria-controls': `wrapped-tabpanel-${index}`,
  };
}


type CommandsState = {
  key: string;
  message: string;
  settings: boolean;
  selectedTab: number;
};

export default class Commands extends React.Component<any, CommandsState> {
  constructor(props: any) {
    super(props);
    this.state = { key: "triage", message: "No message", settings: false, selectedTab: 0 };
    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event: React.SyntheticEvent, newValue: number) {
    console.log(newValue);
    this.setState( {selectedTab: newValue } );
  };

  render() {
    const selectedTab = this.state.selectedTab;

    return (
      <Box >
        <Box sx={{ p: 0 }}>
          <AppBar position="static" sx={{backgroundColor: '#208090'}}>
            <Tabs value={selectedTab} onChange={this.handleChange} aria-label="WCE Triage SPAs" textColor="inherit" indicatorColor="secondary">
              <Tab label="Triage" {...a11yProps(0)} />
              <Tab label="Load Disk Image" {...a11yProps(1)} />
              <Tab label="Create Disk Image" {...a11yProps(2)} />
              <Tab label="Wipe Disk" {...a11yProps(3)} />
              <Tab label="Disk Image" {...a11yProps(4)} />
              <Tab label="Messages" {...a11yProps(5)} />
            </Tabs>
          </AppBar>
          <TabPanel value={selectedTab} index={0} visible={selectedTab === 0} title="Triage">
            <Triage/>
          </TabPanel>
          <TabPanel value={selectedTab} index={1} visible={selectedTab === 1} title="Load">
            <LoadDiskImage/>
          </TabPanel>
          <TabPanel value={selectedTab} index={2} visible={selectedTab === 2} title="Save">
            <SaveDiskImage/>
          </TabPanel>
          <TabPanel value={selectedTab} index={3} visible={selectedTab === 3} title="Wipe">
            <WipeDisk/>
          </TabPanel>
          <TabPanel value={selectedTab} index={4} visible={selectedTab === 4} title="Disk Images">
            <DiskImageManagement/>
          </TabPanel>
          <TabPanel value={selectedTab} index={5} visible={selectedTab === 5} title="Messages">
            <Messages selected={selectedTab === 5}/>
          </TabPanel>
          {/*
          <Tab key="settings" eventKey="settings" title="Settings" disabled={!this.state.settings}>
            <TriageAppSettings/>
          </Tab>
*/}
        </Box>
      </Box>
    );
  }
}
