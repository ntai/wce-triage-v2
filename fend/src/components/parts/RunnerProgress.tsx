import React from 'react';
import {sweetHome} from "../../looseend/home";
import Mui5Table from './Mui5Table';
import {value_to_bgcolor, value_to_color} from "./TriageTableTheme";
import OperationProgressBar from './OperationProgressBar';
import '../commands/commands.css';
import {RunnerStatus, TaskStatus} from "../../types/socket-events";

type RunnerPropsType = {
  runningStatus: undefined | RunnerStatus;
  statuspath: string;
}

type RunnerStateType = {
  sequenceNumber: number | undefined;
  tasks: TaskStatus[];
  taskPages: number;
  tasksLoading: boolean;
  fontSize: number;
}

export default class RunnerProgress extends React.Component<RunnerPropsType, RunnerStateType> {
  constructor(props: any) {
    super(props);
    this.state = {
      /* Status update sequence number */
      sequenceNumber: undefined,

      /* Disk operation tasks (aka tasks) */
      tasks: [],
      /* Page number of the table */
      taskPages: 1,
      /* Loading tasks */
      tasksLoading: true,

      fontSize: 12,
    };

    this.fetchTasks = this.fetchTasks.bind(this);
  }

  componentDidMount() {
    this.fetchTasks()
  }

  componentDidUpdate() {
    if (this.props.runningStatus === undefined) {
      return;
    }

    if (this.state.sequenceNumber === this.props.runningStatus._sequence_)
      return;

    this.setState({sequenceNumber: this.props.runningStatus._sequence_});

    console.log(this.props.runningStatus._sequence_);

    // Every report is a complete, self-sufficient snapshot (see
    // RunnerOutputDispatch's docstring) - just take the full tasks array,
    // there's no per-step delta to patch in.
    if (this.props.runningStatus.tasks !== undefined) {
      this.setState({tasks: this.props.runningStatus.tasks})
    }
  }

  fetchTasks() {
    // Whenever the table model changes, or the user sorts or changes pages, this method gets called and passed the current table model.
    // You can set the `loading` prop of the table to true to use the built-in one or show you're own loading bar if you want.
    this.setState({ tasksLoading: true });
    // Request the data however you want.  Here, we'll use our mocked service we created earlier

    fetch(sweetHome.backendUrl + this.props.statuspath) // "/dispatch/disk-load-status.json"
        .then(reply => reply.json())
        .then(res => {
          // Now just get the rows of data to your React Table (and update anything else like total pages or loading)
          if (res.tasks) {
            this.setState({
              tasks: res.tasks,
              taskPages: res.pages
            });
          }
        })
        .finally( () => {
          this.setState({
            tasksLoading: false,
          });
        });
  }

  render() {
    const {tasks, tasksLoading, fontSize } = this.state;
    if (tasks === undefined)
        return null;

    return (
      <div>
        <Mui5Table<TaskStatus>
          rows={tasks}
          isLoading={tasksLoading}
          style={ {marginTop: 1, marginBottom: 1, minWidth: 750, fontSize: 13, borderRadius: 0, borderWidth: 0, textAlign: "left"} }
          columns={[
            {
              title: "Step",
              render: row => row.taskCategory,
              cellStyle: {fontSize: fontSize, textAlign: "right", minWidth: 300, paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8,},
              headerStyle: { width: 300, },
            },
            {
              title: "Estimate",
              render: row => String(row.taskEstimate),
              cellStyle: {fontSize: fontSize,  minWidth: 80, textAlign: "center", paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8,},
              headerStyle: {
                minWidth: 80,
                maxWidth: 120
              },
            },
            {
              title: "Elapsed",
              render: row => String(row.taskElapse),
              cellStyle: {fontSize: fontSize,  minWidth: 80, textAlign: "center", paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8},
              headerStyle: {
                minWidth: 80,
                maxWidth: 120
              },
            },
            {
              title: 'Status',
              cellStyle: {fontSize: fontSize,  minWidth: 120, paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8 },
              headerStyle: {
                minWidth: 120,
                maxWidth: 160
              },
              render: row => (
                <span>
                  <span style={{
                    color: row.taskStatus === 'waiting' ? value_to_color(0)
                      : row.taskStatus === 'running' ?  value_to_color(1)
                        : row.taskStatus === 'done' ? value_to_color(100)
                          : row.taskStatus === 'fail' ? value_to_color(999)
                            : '#404040',
                    transition: 'all .3s ease'
                  }}>
              &#x25cf;
            </span> {
                  row.taskStatus === 'waiting' ? 'Holding'
                    : row.taskStatus === 'running' ? `In progress`
                    : row.taskStatus === 'done' ? `Completed`
                      : row.taskStatus === 'fail' ? `Failed`
                        : 'Bug'
                }
            </span>
              )
            },
            {
              title: 'Progress',
              cellStyle: {fontSize: fontSize,  minWidth: 120, paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8 },
              headerStyle: {
                minWidth: 120,
                maxWidth: 160
              },
              render: row => (
                <div>
                  <OperationProgressBar value={row.taskProgress} />
                </div>
              )
            },
            {
              title: "Description",
              cellStyle: {fontSize: fontSize,  width: 350, paddingTop: 1, paddingBottom: 1, paddingLeft: 8, paddingRight: 8 },
              headerStyle: {
                width: 350,
              },
              render: row => row.taskMessage,
            }
          ]}
          options={
            {
              paging: false,
              sorting: false,
              draggable: false,
              toolbar: false,
              search: false,
              showTitle: false,
              detailPanelColumnAlignment: "left",
              rowStyle: rowData => { return { backgroundColor: value_to_bgcolor(rowData.taskProgress), paddingTop: 0, paddingBottom: 0, paddingLeft: 8, paddingRight: 8 } },
              headerStyle: { backgroundColor: "#333333", color: "white", borderSpacing: 1 }
            }
          }
          detailPanel={[{
            tooltip: "Show task details",
            render: rowData => {
              if (rowData.taskVerdict) {
                return (
                  <div className="preformat"
                       style={{fontSize: 12, textAlign: 'left', backgroundColor: '#eeeeee', padding: 2}}>
                    {rowData.taskExplain}
                    {rowData.taskVerdict.map(elem => <p>{elem}</p>)}
                  </div>
                )
              } else {
                return (
                  <div className="preformat">
                    {rowData.taskExplain}
                  </div>
                )
              }
            },
          },
          ]
         }
         />
      </div>
    );
  }
}
