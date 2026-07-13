import React from "react";
import {sweetHome} from '../../looseend/home';
import "../commands/commands.css";
import { createStyles, makeStyles } from '@mui/styles';
import { Theme } from '@mui/material/styles';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import {ImageMetaType, ItemType} from "../common/types";

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    formControl: {
      margin: theme.spacing(0),
      minWidth: 180,
    },
    selectEmpty: {
      marginTop: theme.spacing(0),
    },
  }),
);

// <Catalog title={"Restore type"} catalogType={restoreType} catalogTypeChanged={this.setRestoreType} catalogTypesChanged={this.setRestoreTypes} />
// <Catalog title={"Disk image type"} catalogType={this.state.imageType} catalogTypeChanged={this.setImageType} catalogTypesChanged={this.setImageTypes}/>

export default function Catalog( {title, catalogType, catalogTypeChanged, catalogTypesChanged } :
                                     {
                                       title: string,
                                       catalogType?: string,
                                       catalogTypeChanged: (cat?: string) => void,
                                       catalogTypesChanged: (cats: ItemType[]) => void
                                     }) {
  const classes = useStyles();
  const [catalogTypesLoading, setCatalogTypesLoading] = React.useState(true);
  const [catalogTypes, setCatalogTypes] = React.useState<ItemType[]>([]);

  function fetchCatalogTypes() {
    setCatalogTypesLoading(true);

    fetch(sweetHome.backendUrl + "/dispatch/restore-types").then(reply => reply.json()).then(res => {
        const restoreTypes = res.restoreTypes as ImageMetaType[];
        const cats: ItemType[] = restoreTypes.map(rt => ({label: rt.name, value: rt.id}));
        setCatalogTypesLoading(false);
        setCatalogTypes(cats);
        catalogTypesChanged(cats);
        console.log("Setting catalog types\n" + cats.map( (cat) => JSON.stringify(cat)).join("\n"));
    }).finally(() => {
        setCatalogTypesLoading(false);
    });
  }

  React.useEffect(() => {
    fetchCatalogTypes();
  }, []);

  const handleChange = (event: SelectChangeEvent<any>) => {
    catalogTypeChanged(event.target.value);
  };

  const labelId = `catalog-select-label-${title.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <div>
      <FormControl className={classes.formControl}>
        <InputLabel id={labelId}>{title}</InputLabel>
        <Select
          labelId={labelId}
          label={title}
          // handing down undefined doesn't change the selection. Dummy value '' sets it.
          key={catalogType}
          value={catalogType || ''}
          style={{fontSize: 14, textAlign: "left"}}
          onChange={handleChange}
        >
          {catalogTypes.map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
        </Select>
      </FormControl>

    </div>
  );
}
