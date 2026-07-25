import React, { Component } from 'react';
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Button from "@mui/material/Button";
import FormControl from "@mui/material/FormControl";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import OutlinedInput from "@mui/material/OutlinedInput";
import Select, { SelectChangeEvent } from "@mui/material/Select";
import OpenInFullIcon from "@mui/icons-material/OpenInFull";
import { DataGrid, GridColDef, GridPaginationModel, GridSortModel, GridFilterModel } from '@mui/x-data-grid';
import {sweetHome} from '../looseend/home'
import {socket} from './common/socket';
import {SocketEventMap} from '../types/socket-events';
import {LogEntry, LogEventType, LogsResponse, LogFacets} from '../types/api-types';

type MessagesPropsType = {
  selected?: boolean;
}

// Both the polled /logs history and the live 'message' socket event render
// through this one shape - socket-delivered entries (MESSAGE/ERROR only,
// see server.py's send_to_ui()) don't carry a row id/timestamp of their
// own, so those are synthesized on arrival.
type DisplayEntry = {
  key: string;
  timestamp: string;
  type: LogEventType;
  level?: string;
  source?: string;
  message: string;
  data?: Record<string, unknown>;
}

const TYPE_COLORS: Record<LogEventType, string> = {
  ERROR: '#c62828',
  MESSAGE: '#1565c0',
  LOG: '#757575',
  PROGRESS: '#2e7d32',
  PLAN: '#6a1b9a',
  COMMAND_START: '#00695c',
  COMMAND_END: '#00695c',
};

const ALL_TYPES = Object.keys(TYPE_COLORS) as LogEventType[];

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

// Standard Python logging levelnames - see log_store.py's use of record.levelname.
const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

type MessagesStateType = {
  entries: DisplayEntry[];
  total: number;
  sources: string[];
  selectedTypes: LogEventType[];
  selectedLevels: string[];
  paginationModel: GridPaginationModel;
  sortModel: GridSortModel;
  filterModel: GridFilterModel;
  detailData: Record<string, unknown> | null;
}

export default class Messages extends Component<MessagesPropsType, MessagesStateType> {
  constructor(props: MessagesPropsType) {
    super(props);
    this.state = {
      entries: [],
      total: 0,
      sources: [],
      selectedTypes: [],
      selectedLevels: [],
      paginationModel: {page: 0, pageSize: 25},
      sortModel: [{field: 'timestamp', sort: 'desc'}],
      filterModel: {items: []},
      detailData: null,
    }
    this.handleMessage = this.handleMessage.bind(this);
    this.handlePaginationModelChange = this.handlePaginationModelChange.bind(this);
    this.handleSortModelChange = this.handleSortModelChange.bind(this);
    this.handleFilterModelChange = this.handleFilterModelChange.bind(this);
    this.handleTypesChange = this.handleTypesChange.bind(this);
    this.handleLevelsChange = this.handleLevelsChange.bind(this);
    this.handleCloseDetail = this.handleCloseDetail.bind(this);
  }

  componentWillMount() {
    this.fetchFacets();
    this.fetchMessages();
  }

  componentDidUpdate(prevProps: MessagesPropsType) {
    if (this.props.selected && !prevProps.selected) {
      this.fetchMessages();
    }
  }

  /* type/level are fixed/known sets (LOG_LEVELS/ALL_TYPES above), but
     source is open-ended (logger names, runner ids) - fetched once so the
     Source column's filter has real choices to offer. */
  fetchFacets() {
    fetch(sweetHome.backendUrl + '/logs/facets').then(rep => rep.json()).then((res: LogFacets) => {
      this.setState({sources: res.sources});
    });
  }

  /* Pagination, sorting, and filtering (type/level via the standalone
     multi-selects below, source via the grid's own column filter) are all
     server-side: the grid only ever holds the current page's rows,
     everything else is a query param against /logs. */
  fetchMessages() {
    const {paginationModel, sortModel, filterModel, selectedTypes, selectedLevels} = this.state;
    const params = new URLSearchParams();
    params.set('start', String(paginationModel.page * paginationModel.pageSize));
    params.set('count', String(paginationModel.pageSize));
    params.set('sort', sortModel.length > 0 && sortModel[0].sort === 'asc' ? 'asc' : 'desc');

    for (const type of selectedTypes) params.append('type', type);
    for (const level of selectedLevels) params.append('level', level);

    for (const item of filterModel.items) {
      if (item.value === undefined || item.value === null || item.value === '') continue;
      const values: string[] = Array.isArray(item.value) ? item.value : [item.value];
      for (const value of values) {
        if (item.field === 'source') params.append('source', value);
      }
    }

    fetch(sweetHome.backendUrl + '/logs?' + params.toString()).then(rep => rep.json()).then((res: LogsResponse) => {
      const entries: DisplayEntry[] = res.logs.map((log: LogEntry) => ({
        key: 'log-' + log.id,
        timestamp: log.timestamp,
        type: log.type,
        level: log.level ?? undefined,
        source: log.source ?? undefined,
        message: log.message ?? '',
        data: log.data ?? undefined,
      }));
      this.setState({entries: entries, total: res.total});
    });
  }

  /* set up the wock for message */
  componentDidMount() {
    socket.on('message', this.handleMessage);
  }

  componentWillUnmount() {
    socket.off('message', this.handleMessage);
  }

  handleMessage(msg: SocketEventMap["message"]) {
    // Only prepend live: any other page or an active filter means the
    // current view isn't "the unfiltered newest rows" - a live message may
    // not even belong on it, so just leave it for the next fetch/Refresh.
    const {paginationModel, filterModel, sortModel, selectedTypes, selectedLevels} = this.state;
    if (paginationModel.page !== 0 || filterModel.items.length > 0
        || selectedTypes.length > 0 || selectedLevels.length > 0) return;

    const entry: DisplayEntry = {
      key: 'live-' + msg._sequence_,
      timestamp: new Date().toISOString(),
      type: msg.severity === 2 ? 'ERROR' : 'MESSAGE',
      message: msg.message,
    };
    const sortAsc = sortModel.length > 0 && sortModel[0].sort === 'asc';
    const entries = sortAsc ? this.state.entries.concat(entry) : [entry].concat(this.state.entries);
    this.setState({entries: entries, total: this.state.total + 1});
  }

  handlePaginationModelChange(model: GridPaginationModel) {
    this.setState({paginationModel: model}, () => this.fetchMessages());
  }

  handleSortModelChange(model: GridSortModel) {
    this.setState({sortModel: model}, () => this.fetchMessages());
  }

  handleFilterModelChange(model: GridFilterModel) {
    this.setState({filterModel: model, paginationModel: {...this.state.paginationModel, page: 0}}, () => this.fetchMessages());
  }

  handleTypesChange(event: SelectChangeEvent<LogEventType[]>) {
    const value = event.target.value;
    const selectedTypes = (typeof value === 'string' ? value.split(',') : value) as LogEventType[];
    this.setState({selectedTypes, paginationModel: {...this.state.paginationModel, page: 0}}, () => this.fetchMessages());
  }

  handleLevelsChange(event: SelectChangeEvent<string[]>) {
    const value = event.target.value;
    const selectedLevels = typeof value === 'string' ? value.split(',') : value;
    this.setState({selectedLevels, paginationModel: {...this.state.paginationModel, page: 0}}, () => this.fetchMessages());
  }

  handleOpenDetail(data: Record<string, unknown>) {
    this.setState({detailData: data});
  }

  handleCloseDetail() {
    this.setState({detailData: null});
  }

  render() {
    const {entries, total, sources, selectedTypes, selectedLevels, paginationModel, sortModel, filterModel, detailData} = this.state;

    const columns: GridColDef<DisplayEntry>[] = [
      {
        field: 'timestamp',
        headerName: 'Time',
        width: 110,
        valueFormatter: (value: string) => formatTimestamp(value),
      },
      {
        field: 'type',
        headerName: 'Type',
        width: 130,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <span style={{color: TYPE_COLORS[params.value as LogEventType], fontWeight: params.value === 'ERROR' ? 'bold' : 'normal'}}>
            {params.value}
          </span>
        ),
      },
      {
        field: 'level',
        headerName: 'Level',
        width: 90,
        sortable: false,
        filterable: false,
      },
      {
        field: 'source',
        headerName: 'Source',
        width: 140,
        sortable: false,
        type: 'singleSelect',
        valueOptions: sources,
      },
      {
        field: 'message',
        headerName: 'Message',
        flex: 1,
        sortable: false,
      },
      {
        field: 'data',
        headerName: 'Data',
        flex: 1,
        sortable: false,
        filterable: false,
        renderCell: (params) => {
          const value = params.value as Record<string, unknown> | undefined;
          if (!value) return null;
          const json = JSON.stringify(value);
          return (
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, width: '100%', minWidth: 0}}>
              <span style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1}}>
                {json}
              </span>
              <IconButton size="small" onClick={() => this.handleOpenDetail(value)}>
                <OpenInFullIcon fontSize="inherit" />
              </IconButton>
            </Box>
          );
        },
      },
    ];

    return (
      <Box sx={{width: '100%'}}>
        <Box sx={{display: 'flex', gap: 2, mb: 1}}>
          <FormControl size="small" sx={{minWidth: 240}}>
            <InputLabel id="messages-type-filter-label">Type</InputLabel>
            <Select<LogEventType[]>
              labelId="messages-type-filter-label"
              multiple
              value={selectedTypes}
              onChange={this.handleTypesChange}
              input={<OutlinedInput label="Type" />}
              renderValue={(selected) => selected.join(', ')}
            >
              {ALL_TYPES.map(type => (
                <MenuItem key={type} value={type}>
                  <Checkbox checked={selectedTypes.indexOf(type) > -1} />
                  <ListItemText primary={type} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{minWidth: 240}}>
            <InputLabel id="messages-level-filter-label">Level</InputLabel>
            <Select<string[]>
              labelId="messages-level-filter-label"
              multiple
              value={selectedLevels}
              onChange={this.handleLevelsChange}
              input={<OutlinedInput label="Level" />}
              renderValue={(selected) => selected.join(', ')}
            >
              {LOG_LEVELS.map(level => (
                <MenuItem key={level} value={level}>
                  <Checkbox checked={selectedLevels.indexOf(level) > -1} />
                  <ListItemText primary={level} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
        <DataGrid<DisplayEntry>
          rows={entries}
          columns={columns}
          getRowId={row => row.key}
          density="compact"
          className="message-font"
          autoHeight
          rowCount={total}
          paginationMode="server"
          sortingMode="server"
          filterMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={this.handlePaginationModelChange}
          sortModel={sortModel}
          onSortModelChange={this.handleSortModelChange}
          filterModel={filterModel}
          onFilterModelChange={this.handleFilterModelChange}
          pageSizeOptions={[10, 25, 50, 100]}
          showToolbar
        />
        <Dialog open={detailData !== null} onClose={this.handleCloseDetail} maxWidth="md" fullWidth>
          <DialogTitle>Data</DialogTitle>
          <DialogContent dividers>
            <Box
              component="pre"
              sx={{fontFamily: 'monospace', fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0}}
            >
              {detailData ? JSON.stringify(detailData, null, 2) : ''}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={this.handleCloseDetail}>Close</Button>
          </DialogActions>
        </Dialog>
      </Box>
    );
  }
}
