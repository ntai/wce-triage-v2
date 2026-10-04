import React from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, Location, NavigateFunction } from 'react-router-dom';
import Triage from './commands/triage/Triage';
import LoadDiskImage from './commands/load/LoadDiskImage';
import SaveDiskImage from './commands/save/SaveDiskImage';
import Messages from './Messages';
import WipeDisk from "./commands/wipe/WipeDisk";
// import TriageAppSettings from "./settings/TriageAppSettings";

import AppBar from '@mui/material/AppBar';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';
import DiskImageManagement from "./commands/diskimage/DiskImageManagement";


function a11yProps(index: number) {
  return {
    id: `wrapped-tab-${index}`,
    'aria-controls': `wrapped-tabpanel-${index}`,
  };
}

// Each tab is a real route, so a manual browser refresh reloads whichever
// tab the user is looking at instead of always bouncing back to Triage.
// HashRouter keeps this working against the backend's plain StaticFiles
// mount (wce_triage/api/app.py) with no server-side route fallback needed.
const TAB_ROUTES = [
  { path: "/triage", label: "Triage" },
  { path: "/load", label: "Load Disk Image" },
  { path: "/save", label: "Create Disk Image" },
  { path: "/wipe", label: "Wipe Disk" },
  { path: "/diskimage", label: "Disk Image" },
  { path: "/messages", label: "Messages" },
];

type CommandsProps = {
  location: Location;
  navigate: NavigateFunction;
};

class Commands extends React.Component<CommandsProps> {
  constructor(props: CommandsProps) {
    super(props);
    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event: React.SyntheticEvent, newValue: number) {
    this.props.navigate(TAB_ROUTES[newValue].path);
  };

  render() {
    const currentPath = this.props.location.pathname;
    const selectedTab = Math.max(0, TAB_ROUTES.findIndex(tab => tab.path === currentPath));

    return (
      <Box >
        <Box sx={{ p: 0 }}>
          <AppBar position="static" sx={{backgroundColor: '#208090'}}>
            <Tabs value={selectedTab} onChange={this.handleChange} aria-label="WCE Triage SPAs" textColor="inherit" indicatorColor="secondary">
              {TAB_ROUTES.map((tab, index) => (
                <Tab key={tab.path} label={tab.label} {...a11yProps(index)} />
              ))}
            </Tabs>
          </AppBar>
          <Box sx={{p: 1}}>
            <Routes>
              <Route path="/" element={<Navigate to="/triage" replace />} />
              <Route path="/triage" element={<Triage/>} />
              <Route path="/load" element={<LoadDiskImage/>} />
              <Route path="/save" element={<SaveDiskImage/>} />
              <Route path="/wipe" element={<WipeDisk/>} />
              <Route path="/diskimage" element={<DiskImageManagement/>} />
              <Route path="/messages" element={<Messages selected={true}/>} />
              <Route path="*" element={<Navigate to="/triage" replace />} />
            </Routes>
          </Box>
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

// react-router v6 dropped withRouter/class-based route props, so this thin
// function wrapper is what feeds Commands its location/navigate.
export default function CommandsWithRouter() {
  const location = useLocation();
  const navigate = useNavigate();
  return <Commands location={location} navigate={navigate} />;
}
