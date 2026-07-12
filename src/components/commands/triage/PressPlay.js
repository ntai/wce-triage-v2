import React from "react";
import "../commands.css";
import { Button } from '@mui/material'
import Tooltip from '@mui/material/Tooltip';


// stub to run optical test
class OpticalDriveTest {
  play() {}
  pause() {}
}

class PressPlay extends React.Component {
  state = {
    play: false
  };
  player = undefined;

  togglePlay = () => {
    this.props.onPlay();
    this.setState({ play: !this.state.play }, () => {
      if (this.player === undefined)
        this.player = this.props.kind === "mp3" ? new Audio(this.props.url) : new OpticalDriveTest();
      this.state.play ? this.player.play() : this.player.pause();
    });
  };

  render() {
    return (
      <div>
        <Tooltip title={this.props.tooltip}>
        <Button variant={"contained"} size="small" color={"primary"} onClick={this.togglePlay}>{this.props.title  + ": " + (this.state.play ? '\u25a0' : '\u25B6')}</Button>
        </Tooltip>
      </div>
    );
  }
}

export default PressPlay;
