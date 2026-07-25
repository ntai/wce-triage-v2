import React from 'react';
import { lighten } from '@mui/material/styles';
import { makeStyles } from '@mui/styles';
import LinearProgress from '@mui/material/LinearProgress';

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
  const value = props.value;
  const inProgress = value !== undefined && value <= 100;

  const trackColor = inProgress ? lighten('#0080FF', 0.5) : '#F0F0F0';
  const barColor = inProgress
    ? (value !== undefined && value < 100 ? '#0080FF' : '#00E020')
    : (value !== undefined && value > 100 ? '#FF5050' : '#F0F0F0');

  return (
    <div className={classes.root}>
      <LinearProgress
        className={classes.margin}
        variant="determinate"
        value={inProgress && value !== undefined ? value : 100}
        sx={{
          height: 15,
          backgroundColor: trackColor,
          '& .MuiLinearProgress-bar1': {
            borderRadius: 0,
            transition: 'transform 0.1s linear',
            backgroundColor: barColor,
          },
        }}
      />
    </div>
  );
}
