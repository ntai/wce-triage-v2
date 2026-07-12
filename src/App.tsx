import React from 'react';
import Commands from './components/Commands';
import './App.css';
import Grid from '@mui/material/Grid';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import {sweetHome} from "./looseend/home";
import CssBaseline from '@mui/material/CssBaseline';
import { StyledEngineProvider, ThemeProvider, createTheme } from '@mui/material/styles';
import { ThemeProvider as StylesThemeProvider } from '@mui/styles';
import wcelogo from './wcelogo.svg';

const theme = createTheme();

/*
const styles = StyleSheet.create({
  WCE: {
    fontWeight: 'bold',
    fontSize: 30,
  },
  Version: {
    align: "right",
    marginTop: 30,
    marginLeft: 40,
    verticalAlign: "bottom",
    fontSize: 14,
    color: "grey",
  },
  Logo: {width: 500, height: 80, resizeMode: "contain", scale: 1},

  WholeView: {
    marginTop: 0,
    marginLeft: 10,
  },

});
 */

type AppState = {
    frontendVersion: string;
    backendVersion: string;
};

class App extends React.Component {
    state: AppState = {
        frontendVersion: "",
        backendVersion: ""
    };

    constructor(props: any) {
        super(props);
    }

    componentDidMount() {
        fetch(sweetHome.backendUrl + "/version")
            .then(res => res.json())
            .then(result => {
                console.log(result);
                this.setState({
                    backendVersion: result.version.backend,
                    frontendVersion: result.version.frontend
                })
            });
    }

    render() {
        return (
            <StyledEngineProvider injectFirst>
                <ThemeProvider theme={theme}>
                    <StylesThemeProvider theme={theme}>
                        <div className="App bg-white">
                            <CssBaseline/>
                            <Container maxWidth={false}>
                                <Grid container size={12}>
                                    <Grid container size={6}>
                                        <img src={wcelogo} className="App-logo" alt="wcelogo"/>
                                    </Grid>
                                    <Grid size="auto">
                                        <Typography>WCE Triage {this.state.frontendVersion}/{this.state.backendVersion}</Typography>
                                    </Grid>
                                </Grid>

                                <Grid size={12}>
                                    <Commands/>
                                </Grid>

                            </Container>
                        </div>
                    </StylesThemeProvider>
                </ThemeProvider>
            </StyledEngineProvider>
        );
    }
}

export default App;
