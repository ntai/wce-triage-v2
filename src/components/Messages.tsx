import React, { Component } from 'react';
import Grid from "@mui/material/Grid";
import Box from "@mui/material/Box";
import {sweetHome} from '../looseend/home'
import {io} from 'socket.io-client';

type MessagesStateType = {
  messages: string[];
}

export default class Messages extends Component<any, MessagesStateType> {
  constructor(props:any) {
    super(props);
    this.state = {
      messages: []
    }
  }

  componentWillMount() {
    this.fetchMessages();
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
    const wock = io(sweetHome.websocketUrl);
    wock.on('message', this.handleMessage.bind(this));
  }

  handleMessage(msg: any) {
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
