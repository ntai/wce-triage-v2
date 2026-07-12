import React from "react";
import "../commands.css";

class LoadWizard extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      currentStep: 1
    };

    this._next = this._next.bind(this);
    this._prev = this._prev.bind(this);
  }

  _next() {
    let currentStep = this.state.currentStep;
    // Make sure currentStep is set to something reasonable
    if (currentStep >= 2) {
      currentStep = 3;
    } else {
      currentStep = currentStep + 1;
    }

    this.setState({
      currentStep: currentStep
    });
  }

  _prev() {
    let currentStep = this.state.currentStep;
    if (currentStep <= 1) {
      currentStep = 1;
    } else {
      currentStep = currentStep - 1;
    }

    this.setState({
      currentStep: currentStep
    });
  }

  render() {
    /*
        <ChooseImageSource currentStep={currentStep}/>
        <ChooseDisk currentStep={currentStep}/>
        <LoadDetails currentStep={currentStep}/>
        <button onClick={this._next}>Next</button>
        <button onClick={this._prev}>Prev</button>
     */
    return (
      <div>
      </div>
    );
  }
}

