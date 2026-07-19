import React from "react";
import {sweetHome} from '../../looseend/home';
import "../commands/commands.css";
import { createStyles, makeStyles } from '@mui/styles';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select, { SelectChangeEvent } from '@mui/material/Select';

export type ItemType = {
  label: string;
  value: string;
};

const useStyles = makeStyles((theme) =>
  createStyles({
    formControl: {
      margin: theme.spacing(0),
      minWidth: 120,
    },
    selectEmpty: {
      marginTop: theme.spacing(0),
    },
  }),
);




//  title={"Wipe"} wipeOption={wipeOption} wipeOptionChanged={this.selectWipe.bind(this)} wipeOptionsChanged={this.setWipeOptions.bind(this)}
// <WipeOption title={"Wipe"} wipeOption={wipeOption} wipeOptionChanged={this.selectWipe.bind(this)} wipeOptionsChanged={this.setWipeOptions.bind(this)}/>

export default function WipeOption({title, wipeOption, wipeOptionChanged, wipeOptionsChanged} : {
  title: string,
  wipeOption: ItemType|undefined,
  wipeOptionChanged: (item: ItemType|undefined) => void,
  wipeOptionsChanged: (items: ItemType[]) => void
}) {
  const classes = useStyles();
  const [wipeOptionsLoading, setWipeOptionsLoading] = React.useState(true);
  const [wipeOptions, setWipeOptions] = React.useState<ItemType[]>([]);


  function fetchWipeOptions() {
    setWipeOptionsLoading(true);

    fetch(sweetHome.backendUrl + "/dispatch/wipe-types").then(rep => rep.json()).then(res => {
      console.log(res.wipeTypes);
      const wipeTypes : {name: string, id: string}[] = res.wipeTypes as any;
      const wipeOptions = wipeTypes.map(rt => ({label: rt.name, value: rt.id}));
      setWipeOptions(wipeOptions);
      wipeOptionChanged(undefined);
      wipeOptionsChanged(wipeOptions);
    }).finally( () => {
      setWipeOptionsLoading(false);
    });
  }

  React.useEffect(() => {
    console.log("loading wipe options");
    fetchWipeOptions();
  }, []);

  const handleChange = (event: SelectChangeEvent<any>) => {
    if (!event) return;
    if (!event.target) return;
    // setWipeOption(event.target.value);
    if (wipeOptionChanged) wipeOptionChanged(event.target.value);
  };

  return (
    <div>
      <FormControl className={classes.formControl}>
        <InputLabel id="wipe-option-select-label">{title}</InputLabel>
        <Select
          labelId="wipe-option-select-label"
          label={title}
          // handing down undefined doesn't change the selection. Dummy value '' sets it.
          value={wipeOption?.value||"nowipe"}
          style={{fontSize: 12, textAlign: "left"}}
          onChange={handleChange}
        >
          {wipeOptions.map( item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
        </Select>
      </FormControl>

    </div>
  );
}
