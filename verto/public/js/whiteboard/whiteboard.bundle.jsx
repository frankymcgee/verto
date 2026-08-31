import * as React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

class Whiteboard {
  constructor({ page, wrapper }) {
    this.page = page;
    this.wrapper = wrapper;
    this.root = null;

    this.mount();
  }

  mount() {
    const mountElement =
      this.wrapper instanceof HTMLElement
        ? this.wrapper
        : $(this.wrapper).get(0);

    if (!mountElement) {
      throw new Error("Whiteboard mount element was not found.");
    }

    this.root = createRoot(mountElement);
    this.root.render(<App />);
  }

  destroy() {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }
}

frappe.provide("frappe.ui");
frappe.ui.Whiteboard = Whiteboard;

export default Whiteboard;