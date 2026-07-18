import React, { Component } from 'react';
import Grid from "@mui/material/Grid";
import Box from "@mui/material/Box";
import {sweetHome} from '../looseend/home'
import {socket} from './common/socket';
import {SocketEventMap} from '../types/socket-events';

type MessagesPropsType = {
  selected?: boolean;
}

type MessagesStateType = {
  messages: string[];
}

export default class Messages extends Component<MessagesPropsType, MessagesStateType> {
  constructor(props: MessagesPropsType) {
    super(props);
    this.state = {
      messages: []
    }
    this.handleMessage = this.handleMessage.bind(this);
  }

  componentWillMount() {
    this.fetchMessages();
  }

  componentDidUpdate(prevProps: MessagesPropsType) {
    if (this.props.selected && !prevProps.selected) {
      this.fetchMessages();
    }
  }

  /* Initial message loading */
  fetchMessages() {
    // Request the data however you want.
    fetch(sweetHome.backendUrl + '/dispatch/messages').then( rep => rep.json()).then(res => {
      this.setState({messages: res.messages});
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
    const messages = this.state.messages.concat(msg.message);
    console.log("got message." + messages);
    this.setState({messages: messages});
  }

  render() {
    const messages = this.state.messages;

    return (
      <Grid style={{ display: "flex", flex: 1 }} container >
        <Grid style={{ display: "flex", flex: 1 }} size={12}>
          <Box sx={{overflow: "auto", flex: 1, bgcolor: "white", height: "400px"}} id="scroll" className="message-font">
            {messages.map(line => {return (<div>{line}</div>)})}
          </Box>
        </Grid>
      </Grid>
    );
  }
}
