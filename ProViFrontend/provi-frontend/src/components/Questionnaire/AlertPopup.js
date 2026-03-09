import React from 'react';
import { CModal, CModalBody, CModalFooter, CButton } from '@coreui/react';

const AlertPopup = ({ visible, message, onClose }) => {
  return (
    <CModal visible={visible} onClose={onClose}>
      <CModalBody className="bg-red-100 text-red-700 font-semibold text-xl">
      <pre style={{ whiteSpace: "pre-wrap" }}>{message}</pre>
      </CModalBody>
      <CModalFooter>
        <CButton color="danger" onClick={onClose}>
          Close
        </CButton>
      </CModalFooter>
    </CModal>
  );
};

export default AlertPopup;