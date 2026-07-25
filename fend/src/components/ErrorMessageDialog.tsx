import React, {useState} from "react";
import {Button, Dialog, DialogTitle, DialogContent, DialogActions} from "@mui/material";

export default function ErrorMessageModal(errorTitle: string, errorMessage: string) {
  const [isOpen, setIsOpen] = useState(true);
  return (
      <Dialog open={isOpen} >
        <DialogTitle>
          Image loading
        </DialogTitle>
        <DialogContent>
          <h4>{errorTitle}</h4>
          <p>
            {errorMessage}
          </p>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {setIsOpen(false)}}>Close</Button>
        </DialogActions>
      </Dialog>
  );
}
