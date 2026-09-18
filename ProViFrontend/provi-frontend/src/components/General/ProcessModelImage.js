"use client";

import React from "react";

import DefaultProcessModelDiagram from "../../public/images/order_to_cash_model.svg";

const DEFAULT_ALT =
  "Order-to-cash process model (BPMN): Receive Order, Check Credit, Confirm Order, Prepare Shipment, Issue Invoice, Ship Order, Receive Payment, Cancel Order";

// The experiment's process model: the admin-uploaded image when there is one,
// otherwise the bundled order-to-cash diagram. Uploaded SVGs go through <img>
// rather than being inlined, so any script inside them never runs.
export default function ProcessModelImage({ url, style }) {
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="Process model used in this study" style={style} />;
  }
  return <DefaultProcessModelDiagram role="img" aria-label={DEFAULT_ALT} style={style} />;
}
