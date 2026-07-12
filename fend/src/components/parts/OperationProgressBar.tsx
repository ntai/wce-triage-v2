import React from 'react';
import { lighten } from '@mui/material/styles';
import { makeStyles, withStyles } from '@mui/styles';
import LinearProgress from '@mui/material/LinearProgress';

const OperationProgress = withStyles({
  root: {
    height: 15,
    backgroundColor: lighten('#0080FF', 0.5),
  },
  bar: {
    borderRadius: 0,
    transition: 'transform 0.1s linear',
  },
  barColorPrimary: {
    backgroundColor: '#00E020'
  },
  barColorSecondary: {
    backgroundColor: '#0080FF'
  },
})(LinearProgress);


const NoProgress = withStyles({
  root: {
    height: 15,
    backgroundColor: '#F0F0F0'
  },
  bar: {
    borderRadius: 0,
    transition: 'transform 0.1s linear',
  },
  barColorPrimary: {
    backgroundColor: '#FF5050'
  },
  barColorSecondary: {
    backgroundColor: '#F0F0F0'
  },
})(LinearProgress);


const useStyles = makeStyles(theme => ({
  root: {
    flexGrow: 1,
  },
  margin: {
    margin: theme.spacing(1),
  },
}));

type OperationProgressBarProps = {
  value: number | undefined;
};

export default function OperationProgressBar(props: OperationProgressBarProps) {
  const classes = useStyles();

  return (
    <div className={classes.root}>
      {
        (props.value !== undefined && props.value <= 100) ?
          <OperationProgress
            className={classes.margin}
            variant="determinate"
            color={props.value < 100 ? "secondary": "primary"}
            value={props.value}
          />
          :
          <NoProgress
            className={classes.margin}
            variant="determinate"
            color={props.value !== undefined && props.value > 100 ? "primary" : "secondary"}
            value={100}
          />
      }
    </div>
  );
}
