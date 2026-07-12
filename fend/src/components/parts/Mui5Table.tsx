import React, {CSSProperties} from 'react';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import IndeterminateCheckBoxIcon from '@mui/icons-material/IndeterminateCheckBox';
import CheckBoxIcon from '@mui/icons-material/CheckBox';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import * as Immutable from 'immutable';


// type MaybeRowData<RowType> = RowType | Promise<RowType>;
type MaybeRowData<RowType> = RowType;

const selectionPropsDefaults: object = {size: "small"};
const detailPanelPropsDefaults: object = {size: "small",};

const selectionCellStyleDefaults: React.CSSProperties = {padding: "4px", width: "38px"};
const detailsToggleCellStyleDefaults: React.CSSProperties = {padding: "4px", width: "38px"};


export type Mui5TableColumn<RowType> = {
    title: string;
    render: (row: MaybeRowData<RowType>, index: number) => string | JSX.Element | null | undefined;
    cellStyle?: CSSProperties;
    headerStyle?: CSSProperties;
}

export interface Mui5TableOptions<RowType> {
    draggable?: Boolean,
    paging?: Boolean,
    sorting?: Boolean,
    toolbar?: Boolean,
    search?: Boolean,
    showTitle?: Boolean,
    detailPanelColumnAlignment?: "left" | "center" | "right",
    rowStyle?: CSSProperties | ((rowData: RowType, index: number) => CSSProperties),
    selection?: Boolean,
    headerStyle?: CSSProperties,
    size?: "small" | "medium" | string;
    selectionProps?: ((rowData: RowType, index: number) => object),
}

export type Mui5TableDetailPanel<RowType> = {
    render: (row: MaybeRowData<RowType>, index: number) => JSX.Element;
    icon?: JSX.Element;
    openIcon?: JSX.Element;
    tooltip?: string;
    title?: string;
    panelStyle?: CSSProperties;
}

export interface Mui5TableProps<RowType> {
    columns: Mui5TableColumn<RowType>[],
    icons?: object,
    rows: MaybeRowData<RowType>[],
    options?: Mui5TableOptions<RowType>,
    detailPanel?: Mui5TableDetailPanel<RowType>[],
    isLoading?: boolean,
    style?: CSSProperties,
    onSelectionChange?: (rowIndex: number|"all", selected: boolean) => void,
    isSelected?: (rowIndex: number, row: RowType) => boolean,
    totalSelections?: () => number,
    nSelectables?: () => number,
}


function Mui5HeaderCell<RowType>({column, index:_, tableHeaderStyle}: { column: Mui5TableColumn<RowType>, index: number, tableHeaderStyle?: CSSProperties }) {
    return (
        <TableCell style={{...tableHeaderStyle, ...column.headerStyle}}>
            {column.title}
        </TableCell>);
}


function Mui5Cell<RowType>({
                               column,
                               row,
                               index
                           }: { column: Mui5TableColumn<RowType>, row: MaybeRowData<RowType>, index: number }) {
    return (
        <TableCell style={column.cellStyle}>
            {column.render(row, index)}
        </TableCell>);
}


function getPanelToggle(panelToggles: Immutable.Map<number, Immutable.List<boolean>>, rowIndex: number, panelIndex: number): boolean {
    const currentSelection: Immutable.List<boolean> | undefined = panelToggles.get(rowIndex);
    if (currentSelection) {
        return currentSelection.get(panelIndex) ? true : false;
    }
    return false;
}

function setPanelToggle(value: boolean, panelToggles: Immutable.Map<number, Immutable.List<boolean>>, rowIndex: number, panelIndex: number): Immutable.Map<number, Immutable.List<boolean>> | undefined {
    const currentSelection: Immutable.List<boolean> | undefined = panelToggles.get(rowIndex);
    if (currentSelection) {
        const currentValue = currentSelection.get(panelIndex);
        if (currentValue !== value)
            return panelToggles.set(rowIndex, currentSelection.set(panelIndex, value));
    } else {
        if (value) {
            const zero = Immutable.List.of<boolean>();
            return panelToggles.set(rowIndex, zero.set(panelIndex, true));
        }
    }
    return undefined;
}

/*
 * Detail panel toggle
 */
function Mui5DetailPanelToggle({panelToggles, setPanelToggles, rowIndex, panelIndex}: {
    panelToggles: Immutable.Map<number, Immutable.List<boolean>>,
    setPanelToggles: (_: Immutable.Map<number, Immutable.List<boolean>>) => void,
    rowIndex: number,
    panelIndex: number
}) {
    function toggleOpen() {
        const toggled = !getPanelToggle(panelToggles, rowIndex, panelIndex);
        const changed = setPanelToggle(toggled, panelToggles, rowIndex, panelIndex);
        if (changed)
            setPanelToggles(changed);
    }

    return (
        <TableCell {...detailPanelPropsDefaults} sx={detailsToggleCellStyleDefaults} >
                <IconButton aria-label="expand row" size="small" onClick={toggleOpen} style={{padding: "2px"}}>
                    {getPanelToggle(panelToggles, rowIndex, panelIndex) ? <KeyboardArrowDownIcon /> :
                        <KeyboardArrowUpIcon  />}
                </IconButton>
        </TableCell>);
}


function Mui5TableSelectionCell({isSelected, onSelectionChange, rowIndex, selectionProps}: {
    isSelected: (rowIndex: number) => boolean,
    rowIndex: number,
    onSelectionChange: (rowIndex: number, selected: boolean) => void,
    selectionProps?: object,
}) {
    function toggleSelection() {
        const newSelection = !isSelected(rowIndex);
        onSelectionChange(rowIndex, newSelection);
    }

    return (
        <TableCell style={selectionCellStyleDefaults}>
                <IconButton
                    aria-label="select this row"
                    onClick={toggleSelection}
                    size="small"
                    {...selectionProps}
                >
                    {isSelected(rowIndex) ? <CheckBoxIcon/> : <CheckBoxOutlineBlankIcon/>}
                </IconButton>
        </TableCell>);
}


function ComputeSelectionHeaderCell<RowType>(options: Mui5TableOptions<RowType>,
                                             nSelections: number,
                                             nSelectables: number,
                                             nRows: number,
                                             selectionCB: (nSelections: number, nSelectables: number, nRows: number) => void,
                                             selectionProps?: object) {
    if (!options?.selection) {
        return null;
    }

    function toggleSelection() {
        selectionCB(nSelections, nSelectables, nRows);
    }

    return (
        <TableCell style={{...options?.headerStyle, ...selectionCellStyleDefaults}}>
                <IconButton
                    aria-label="selection header"
                    onClick={toggleSelection}
                    style={{color: options?.headerStyle?.color}}
                    {...selectionProps}
                >
                    {nSelectables === nSelections ? <CheckBoxIcon/> : ((nSelections === 0) ? <CheckBoxOutlineBlankIcon/> :
                        <IndeterminateCheckBoxIcon/>)}
                </IconButton>
        </TableCell>);
}



export default function Mui5Table<RowType>(props: Mui5TableProps<RowType>) {
    const [panelToggles, setPanelToggles] = React.useState(Immutable.Map<number, Immutable.List<boolean>>());

    const {rows, columns, options, detailPanel, style, onSelectionChange, isSelected, totalSelections, nSelectables} = props;

    function rowIsSelected(rowIndex: number) : boolean {
        return isSelected ? isSelected(rowIndex, rows[rowIndex]) : false;
    }

    if (rows === undefined || rows === null) {
        console.log("table - no rows")
        return null;
    }
    if (!Array.isArray(rows)) {
        console.log("table - rows is not array")
        console.log(rows)
        return null;
    }
    const {headerStyle} = Object.assign({}, {}, options);
    const detailHeaderColumn = detailPanel ? (<TableCell style={headerStyle} />) : null;
    const selectionHeaderColumn = options?.selection ? ComputeSelectionHeaderCell(
        options,
        totalSelections ? totalSelections() : 0,
        nSelectables ? nSelectables() : rows.length,
        rows.length,
        onRowsSelectionCB,
        selectionPropsDefaults) : null;
    const tableSize = options?.size ? (options.size === "small" ? "small" : "medium") : "small";

    // Total column count, used so the detail-panel row's single cell can span the full table width.
    const totalColumnCount = columns.length + (options?.selection ? 1 : 0) + (detailPanel ? detailPanel.length : 0);

    function onRowSelectionChange(rowIndex: number, selected: boolean) {
        if (onSelectionChange) {
            onSelectionChange(rowIndex, selected);
        }
    }

    function onRowsSelectionCB(nSelections: number, nRows: number) {
        if (!onSelectionChange)
            return;

        if (nRows > 0) {
            // There are some rows.
            onSelectionChange("all", nSelections !== nRows);
        } else {
            onSelectionChange("all", false);
        }
    }

    return (
        <React.Fragment>

            <TableContainer component={Paper}>
                <Table size={tableSize} aria-label="unnamed table" style={style}>
                    <TableHead style={headerStyle}>
                        <TableRow key={"table-header"} sx={{ '& > *': { borderBottom: 'unset' } }}>
                            {selectionHeaderColumn}
                            {detailHeaderColumn}
                            {
                                columns.map((column, index) =>
                                    <Mui5HeaderCell key={index} column={column} index={index} tableHeaderStyle={headerStyle} />)
                            }
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        { rows.map((row, rowIndex) => {
                            if (row === null || row === undefined) {
                                console.warn(`row[${rowIndex}] is null or undefined.`);
                                return null;
                            }
                            const selectionProps = Object.assign({}, selectionPropsDefaults,
                                options?.selectionProps ? (options.selectionProps instanceof Function ? options.selectionProps(row, rowIndex) : options.selectionProps) : {});

                            const maybeRowStyle = options?.rowStyle;
                            const rowStyle = (maybeRowStyle instanceof Function) ? maybeRowStyle(row, rowIndex) : maybeRowStyle;

                            return (
                                <React.Fragment key={`table-row-fragment-${rowIndex}`}>
                                    <TableRow key={`table-row-${rowIndex}`} sx={rowStyle}>
                                        {(options?.selection) ? <Mui5TableSelectionCell
                                            isSelected={rowIsSelected}
                                            onSelectionChange={onRowSelectionChange}
                                            rowIndex={rowIndex}
                                            selectionProps={selectionProps}
                                        /> : null}
                                        {
                                            (detailPanel) ? detailPanel.map((panel, panelIndex) =>
                                                <Mui5DetailPanelToggle
                                                    key={panelIndex}
                                                    panelToggles={panelToggles}
                                                    setPanelToggles={setPanelToggles}
                                                    rowIndex={rowIndex}
                                                    panelIndex={panelIndex}
                                                />) : null
                                        }
                                        {
                                            columns.map((column, index) => <Mui5Cell key={index} column={column} row={row} index={index} />)
                                        }
                                    </TableRow>
                                    {
                                        detailPanel ? detailPanel.map((panel, panelIndex) => {
                                            const rendered = panel.render(row, panelIndex);
                                            if (rendered) {
                                                return (
                                                    <TableRow key={`table-row-detail-${rowIndex}-${panelIndex}`}>
                                                        <TableCell style={{padding: 0}}
                                                                   colSpan={totalColumnCount}>
                                                            <Collapse
                                                                in={getPanelToggle(panelToggles, rowIndex, panelIndex)}
                                                                timeout="auto" unmountOnExit>
                                                                {rendered}
                                                            </Collapse>
                                                        </TableCell>
                                                    </TableRow>
                                                )
                                            } else {
                                                return null;
                                            }
                                        }) : null
                                    }
                                </React.Fragment>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        </React.Fragment>
    );
}
