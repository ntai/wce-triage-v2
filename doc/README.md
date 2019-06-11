# WCE Triage/Installer

Overall design -

User interface is done by web browser using React.js.

## Backend - 

### Triaging
it's done by running Python script as before. 
Result is generated as json file, and served by a simple HTTP server by Python

### Loading

Using websocket (Python3 websockets).
