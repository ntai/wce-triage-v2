import React from "react";
import "../commands.css";
import { Button } from '@mui/material'
import Tooltip from '@mui/material/Tooltip';


// stub to run optical test
class OpticalDriveTest {
  play() {}
  pause() {}
}

type PressPlayProps = {
  title: string;
  tooltip: string;
  kind: "mp3" | "optical";
  url: string;
  onPlay: () => void;
};

type PressPlayState = {
  play: boolean;
};

class PressPlay extends React.Component<PressPlayProps, PressPlayState> {
  state: PressPlayState = {
    play: false
  };
  player: HTMLAudioElement | OpticalDriveTest | undefined = undefined;

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
        <Button variant={"contained"} size="small" color={"primary"} onClick={this.togglePlay}>{this.props.title  + ": " + (this.state.play ? '■' : '▶')}</Button>
        </Tooltip>
      </div>
    );
  }
}

export default PressPlay;
