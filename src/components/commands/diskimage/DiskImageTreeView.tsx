import React from 'react';
import { makeStyles } from '@mui/styles';
import Typography from '@mui/material/Typography';
import {sweetHome} from "../../../looseend/home";
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem, TreeItemProps } from '@mui/x-tree-view/TreeItem';
import Label from '@mui/icons-material/Label';
import Checkbox from "@mui/material/Checkbox";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import CancelIcon from "@mui/icons-material/Cancel";
import KeyboardIcon from "@mui/icons-material/Keyboard";
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import ArchiveIcon from '@mui/icons-material/Archive';
import DeleteIcon from '@mui/icons-material/Delete';
import {DeviceSelectionType, ImageMetaType} from "../../common/types";
import {SourceType, ToDiskSources} from "./DiskImageSelector";

const useTreeItemStyles = makeStyles((theme) => ({
  root: {
    color: theme.palette.text.secondary,
    '&:focus > $content': {
      backgroundColor: `var(--tree-view-bg-color, ${theme.palette.grey[400]})`,
      color: 'var(--tree-view-color)',
    },
  },
  content: {
    color: theme.palette.text.secondary,
    borderTopRightRadius: theme.spacing(2),
    borderBottomRightRadius: theme.spacing(2),
    paddingRight: theme.spacing(1),
    fontWeight: "bold",
    '&.Mui-expanded': {
      fontWeight: "normal",
    },
  },
  groupTransition: {
    marginLeft: 0,
    '& $content': {
      paddingLeft: theme.spacing(2),
    },
  },
  label: {
    fontWeight: 'inherit',
    color: 'inherit',
  },
  labelRoot: {
    display: 'flex',
    alignItems: 'center',
    padding: theme.spacing(0.5, 0),
  },
  labelIcon: {
    marginRight: theme.spacing(1),
  },
  labelText: {
    fontWeight: 'inherit',
    flexGrow: 1,
  },
}));

/*
StyledTreeItem.propTypes = {
  bgColor: PropTypes.string,
  color: PropTypes.string,
  labelIcon: PropTypes.elementType.isRequired,
  labelInfo: PropTypes.string,
  labelText: PropTypes.string.isRequired,
  itemId: PropTypes.string.isRequired
};
*/


type StyledTreeItemProps = {
  labelText: string;
  labelIcon: JSX.Element;
  selected?: boolean;
  handleChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  value?: string;
  itemId: string
}


function StyledTreeItem(props: TreeItemProps & StyledTreeItemProps) {
  const classes = useTreeItemStyles();
  const { labelText, labelIcon, selected, handleChange, value, itemId, ...other } = props;

  let checkbox = null;
  if (value) {
    checkbox = <Checkbox
      checked={selected === undefined ? false : selected}
      onChange={handleChange}
      value={value}
      id={value}
      slotProps={{
        input: {
          'aria-label': 'primary checkbox',
        },
      }}
    />
  }

  return (
    <TreeItem
      itemId={itemId}
      key={itemId}
      label={
        <div className={classes.labelRoot}>
          {labelIcon}
          {checkbox}
          <Typography variant="body2" className={classes.labelText} align={"left"}>
            {labelText}
          </Typography>
        </div>
      }
      classes={{
        root: classes.root,
        content: classes.content,
        groupTransition: classes.groupTransition,
        label: classes.label,
      }}
      {...other}
    />
  );
}

interface AlertDialogProps {
  title?: string;
  message?: string;
  closelabel?: string;
}

function AlertDialog({title, message, closelabel}: AlertDialogProps) {
  const [open, setOpen] = React.useState( false);

  React.useEffect(() => {
    if (message !== undefined)
      setOpen(true);
  }, [message]);

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <div>
      <Dialog
        open={open}
        onClose={handleClose}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{title || "Error notification"}</DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            {message}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} color="primary" autoFocus>
            {closelabel || "Close" }
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  ) }


interface ImageFileItemProps {
  imageFile: SourceType;
  selectionChanged: (event: React.ChangeEvent<HTMLInputElement>) => void;
  selected?: boolean;
  catalog: string;
  handleItemRename: (item: SourceType) => void;
  handleItemDelete: (item: SourceType) => void;
}

function ImageFileItem(props: ImageFileItemProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [origin, setOrigin] = React.useState({x:0, y:0});

  const {imageFile, selectionChanged, selected, catalog, handleItemRename,handleItemDelete} = props;

  const handleItemClick = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setOrigin({x: event.clientX - 2, y: event.clientY - 4});
    setIsOpen(true);
  };

  const handleMenuClose = () => {
    setIsOpen(false);
  };

  return (
    <div onContextMenu={handleItemClick} style={{ cursor: 'context-menu' }}>
      <StyledTreeItem selected={selected} itemId={catalog + "/" + imageFile.label} value={imageFile.label} handleChange={selectionChanged} labelText={imageFile.label} labelIcon={<ArchiveIcon/>} />
      <Menu
        keepMounted
        open={isOpen}
        onClose={handleMenuClose}
        anchorReference="anchorPosition"
        anchorPosition={{top: origin.y, left: origin.x}}
      >
        <MenuItem onClick={(_) => {setIsOpen(false); handleItemRename(imageFile);}}>Rename</MenuItem>
        <MenuItem onClick={(_) => {setIsOpen(false); handleItemDelete(imageFile);}}>Delete</MenuItem>
      </Menu>
    </div>
  );
}

function RenameDialog(props:any) {
  const filename = props.filename;
  const targetImageFile = props.targetImageFile;
  const [value, setValue] = React.useState(filename);
  const setOpen = props.setOpen;
  const submitRename = props.submitRename;
  const is_open = props.open;


  const handleClose = () => {
    setOpen(false);
  };

  const handleRename = () => {
    setOpen(false);
    submitRename(value, targetImageFile);
  };

  const handleChange = (event: any) => {
    setValue(event.target.value);
  };

  return (
    <div>
      <Dialog open={is_open} onClose={handleClose} aria-labelledby="form-dialog-title">
        <DialogTitle id="form-dialog-title">Rename File</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Current filename: {filename}
          </DialogContentText>
          <TextField
            defaultValue={filename}
            autoFocus
            margin="dense"
            id="filename"
            label="New file name"
            type="text"
            fullWidth
            onChange={handleChange}
          />
        </DialogContent>
        <DialogActions>
          <Button startIcon={<CancelIcon />} onClick={handleClose} color="primary">
            Cancel
          </Button>
          <Button startIcon={<KeyboardIcon />} color="primary" disabled={value==="" || value === filename || value[0] === "." || value[0] === "/"} onClick={handleRename} >
            Rename
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}



function DeleteDialog(props: {
  open: boolean,
  filename: string,
  targetImageFile?: SourceType,
  setOpen: (open: boolean) => void,
  submitDelete: (source: SourceType) => void
}) {

  const filename = props.filename;
  const targetImageFile = props.targetImageFile;
  const [value, setValue] = React.useState(filename);
  const setOpen = props.setOpen;
  const submitDelete = props.submitDelete;

  const handleClose = () => {
    setOpen(false);
  };

  const handleDelete = () => {
    setOpen(false);
    if (targetImageFile)
      submitDelete(targetImageFile);
  };

  const handleChange = (event: any) => {
    setValue(event.target.value);
  };

  return (
    <div>
      <Dialog open={props.open} onClose={handleClose} aria-labelledby="form-dialog-title">
        <DialogTitle id="form-dialog-title">Delete Image File</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Filename: {filename}
          </DialogContentText>
          <TextField
            value={filename}
            autoFocus
            margin="dense"
            id="filename"
            label="Deleting filename"
            type="text"
            fullWidth
            onChange={handleChange}
          />
        </DialogContent>
        <DialogActions>
          <Button startIcon={<CancelIcon />} onClick={handleClose} color="primary">
            Cancel
          </Button>
          <Button startIcon={<DeleteIcon />} color="primary" disabled={value==="" || value[0] === "." || value[0] === "/"}  onClick={handleDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}



const diskImageViewStyle = makeStyles({
  root: {
    minHeight: 264,
    flexGrow: 1,
    maxWidth: 800,
  },
});

// Leaf tree items (no children) get this blank spacer instead of an expand/collapse arrow.
function TreeEndIconSpacer() {
  return <div style={{width: 24}}/>;
}


type CatalogIndexType = { [restoreType: string]: SourceType[] };

function CatalogList(props: {
  catalogTypes: ImageMetaType[],
  catalogIndex: CatalogIndexType,
  selectionChanged: (event: React.ChangeEvent<HTMLInputElement>) => void,
  handleRenameCommand: (source: SourceType) => void,
  handleDeleteCommand: (source: SourceType) => void,
  onCatalogClick: (catalog_id: string) => void,
  selection: DeviceSelectionType<boolean>
}) {
  const { catalogTypes, catalogIndex, selectionChanged, handleRenameCommand, handleDeleteCommand, onCatalogClick, selection} = props;

  function fileList(id: string) {
    let files = [];
    if (catalogIndex[id] && catalogIndex[id].length)
      files = catalogIndex[id];
    else
      return null;

    return files.map(imageFile => {
      return <ImageFileItem catalog={id} imageFile={imageFile} selectionChanged={selectionChanged}
                            selected={selection[imageFile.label]}
                            handleItemRename={handleRenameCommand}
                            handleItemDelete={handleDeleteCommand}/>
    });
  }

  return (<div>
    {
      catalogTypes.map(function (catalog) {
        if (!catalog.id) return null;
        const catalog_id = catalog.id;
        return (
          <StyledTreeItem
              itemId={catalog.id} labelText={catalog.name} labelIcon={<Label />}
              onClick={(_: React.MouseEvent) => onCatalogClick(catalog_id)}
          >
            {fileList(catalog.id)}
           </StyledTreeItem>
        )
    } ) }
    </div>);
}

export type DiskImageOperationType = "expand" | "collapse" | "selectall" | "deselectall";

export default function DiskImageTreeView(
    {command, clearCommand, selectionChangedCB} :
        {
          command?: DiskImageOperationType,
          clearCommand: () => void,
          selectionChangedCB: (selection: DeviceSelectionType<boolean>) => void
        }) {
  const classes = diskImageViewStyle();

  const [sources, setSources] = React.useState<SourceType[]>([]);
  const [sourcesLoading, setSourcesLoading] = React.useState(true);
  const [catalogTypesLoading, setCatalogTypesLoading] = React.useState(true);
  const [catalogTypes, setCatalogTypes] = React.useState<ImageMetaType[]>([]);
  const [catalogIndex, setCatalogIndex] = React.useState<CatalogIndexType>({});
  const [selection, setSelection] = React.useState< DeviceSelectionType<boolean> > ({});
  const [expandedCategories, setExpandedCategories] = React.useState<string[]>([]);
  const [renameDialogOpen, renameDialogSetOpen] = React.useState(false);
  const [deleteDialogOpen, deleteDialogSetOpen] = React.useState(false);
  const [targetImageFile, setTargetImageFile] = React.useState<SourceType|undefined>(undefined);
  const [alertTitle, setAlertTitle] = React.useState<string|undefined>(undefined);
  const [alertMessage, setAlertMessage] = React.useState<string|undefined>(undefined);
  const [alertClose, setAlertClose] = React.useState<string|undefined>(undefined);


  React.useEffect(() => {
    fetchCatalogTypes();
    fetchSources();
  }, []);

  function fetchSources() {
    setSourcesLoading(true);

    fetch(sweetHome.backendUrl + "/dispatch/disk-images").then( rep => rep.json()).then(res => {
      const srcs = ToDiskSources(res.sources as any, 10000);
      setSources(srcs);
      setSourcesLoading(false);
    });
  }

  function fetchCatalogTypes() {
    setCatalogTypesLoading(true);
    fetch(sweetHome.backendUrl + "/dispatch/restore-types").then(rep => rep.json()).then(res => {
      const restoreTypes = res.restoreTypes as ImageMetaType[];
      // const cats: ItemType[] = restoreTypes.map(rt => ({label: rt.name, value: rt.id}));
      setCatalogTypes(restoreTypes);
    })
        .finally( () => { setCatalogTypesLoading(false); });
  }


  function updateCatalogIndex() {
    if (!sourcesLoading && !catalogTypesLoading) {
      let catind: CatalogIndexType = {};

      if (catalogTypes) {
        let cat;
        for (cat of catalogTypes)
          catind[cat.id] = [];
      }
      for (let src of sources) {
        if (catind[src.restoreType])
          catind[src.restoreType].push(src);
        else
          catind[src.restoreType] = [src];
      }
      setCatalogIndex(catind);
      setExpandedCategories([]);
    }
  }

  function handleRenameCommand(imageFile: SourceType) {
    console.log(imageFile);
    setAlertMessage(undefined);
    setTargetImageFile(imageFile);
    renameDialogSetOpen(true);
  }

  function submitRename(filename: string, targetImageFile: SourceType) {
    console.log(filename);
    console.log(targetImageFile);

    const url = encodeURI(sweetHome.backendUrl + "/dispatch/rename?to=" + filename + "&restoretype=" + targetImageFile.restoreType + "&from=" + targetImageFile.label);
    fetch(url, {"method": "POST"}).then(rep => rep.json()).then(res => {
      console.log(res);
      setAlertMessage(undefined);
      fetchSources();
    }).catch(err => {
      console.log(err);
      setAlertClose("Bummer");
      setAlertTitle("Rename Failure");
      setAlertMessage("Renaming " + filename + " failed.");
    }).finally( () => renameDialogSetOpen(false) );
  }

  function handleDeleteCommand(imageFile: SourceType) {
    console.log(imageFile);
    setAlertMessage(undefined);
    setTargetImageFile(imageFile);
    deleteDialogSetOpen(true);
  }

  function submitDelete(targetImageFile: SourceType) {
    const filename = targetImageFile.label;
    console.log( "Deleting " + filename);

    const url = encodeURI(sweetHome.backendUrl + "/dispatch/delete?name=" + filename + "&restoretype=" + targetImageFile.restoreType);
    fetch(url, {"method": "POST"}).then( rep => rep.json()).then(res => {
        console.log(res);
      setAlertMessage(undefined);
      fetchSources();
    }).catch(err  => {
      console.log(err);
      setAlertClose("Bummer");
      setAlertTitle("File Deletion Failure");
      setAlertMessage("Deleting " + filename + " failed.");
    }).finally( () => deleteDialogSetOpen(false));
  }


  React.useEffect(() => {
    updateCatalogIndex();
  }, [sourcesLoading, catalogTypesLoading, catalogTypes, sources]);


  React.useEffect(() => {
    if (!catalogTypesLoading && !sourcesLoading && command !== undefined) {

      if (command === "expand") {
        setExpandedCategories(catalogTypes.map(cat => cat.id));
      }

      if (command === "collapse") {
        setExpandedCategories([]);
      }

      if (command === "selectall") {
        let src: SourceType;
        let newSelection: DeviceSelectionType<boolean> = {};
        for (src of sources)
          newSelection[src.label] = true;
        setSelection(newSelection);
        if (selectionChangedCB)
          selectionChangedCB(newSelection);
      }

      if (command === "deselectall") {
        setSelection({});
        if (selectionChangedCB)
          selectionChangedCB({});
      }
      clearCommand();
    }
  }, [command]);


  function selectionChanged(event: React.ChangeEvent<HTMLInputElement>) {
    if (!sourcesLoading && !catalogTypesLoading) {
      let newSelection: DeviceSelectionType<boolean> = Object.assign({}, selection);
      newSelection[event.target.value] = event.target.checked;
      setSelection(newSelection);
      if (selectionChangedCB)
        selectionChangedCB(newSelection);
    }
  }

  function onCatalogClick(catalog_id: string) {
    if (catalogTypes) {
      const expanded = expandedCategories.filter(id => catalog_id === id).length === 1;

      if (expanded) {
        setExpandedCategories(expandedCategories.filter(id => catalog_id !== id));
      }
      else {
        const newExpandedCategories = expandedCategories.map(id => id);
        newExpandedCategories.push(catalog_id);
        setExpandedCategories(newExpandedCategories);
      }
    }
  }

  if (!sourcesLoading && !catalogTypesLoading) {
    return (
      <div>
        <SimpleTreeView
          className={classes.root}
          expandedItems={expandedCategories}
          slots={{
            collapseIcon: ArrowDropDownIcon,
            expandIcon: ArrowRightIcon,
            endIcon: TreeEndIconSpacer,
          }}
        >
          <CatalogList catalogTypes={catalogTypes}
                       catalogIndex={catalogIndex}
                       selectionChanged={selectionChanged}
                       handleRenameCommand={handleRenameCommand}
                       handleDeleteCommand={handleDeleteCommand}
                       onCatalogClick={onCatalogClick}
                       selection={selection} />
        </SimpleTreeView>
        <RenameDialog open={renameDialogOpen} setOpen={renameDialogSetOpen} submitRename={submitRename}
                      filename={targetImageFile ? targetImageFile.label : ""} targetImageFile={targetImageFile}/>
        <DeleteDialog open={deleteDialogOpen} setOpen={deleteDialogSetOpen} submitDelete={submitDelete}
                      filename={targetImageFile ? targetImageFile.label : ""} targetImageFile={targetImageFile}/>
        <AlertDialog title={alertTitle} message={alertMessage} closelabel={alertClose} />
      </div>
    );
  } else {
    return null;
  }
}
