import * as React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

class Whiteboard {
  constructor({ page, wrapper, ...options }) {
    this.options = options;
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

    // Desk can reuse a cached Page script that passes the outer page wrapper.
    // Establish the containing block here as well as in the current page script.
    mountElement.classList.add("verto-whiteboard-host");

    // Let Desk control the width (including collapsed/expanded sidebars).
    // Only the remaining viewport height needs to be measured here.
    this.resize = () => {
      const top = mountElement.getBoundingClientRect().top;
      const height = `${Math.max(0, window.innerHeight - top)}px`;
      if (mountElement.style.height !== height) {
        mountElement.style.height = height;
      }
    };
    this.resize();
    window.addEventListener("resize", this.resize);

    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(mountElement);
    // Header height can change without a window resize (banners or wrapping).
    const pageHead = this.page?.page_head?.get(0);
    const deskHeader = mountElement.closest(".main-section")?.querySelector("header");
    if (pageHead) this.resizeObserver.observe(pageHead);
    if (deskHeader) this.resizeObserver.observe(deskHeader);

    this.root = createRoot(mountElement);
    this.root.render(<App {...this.options} />);
  }

  destroy() {
    this.resizeObserver?.disconnect();
    window.removeEventListener("resize", this.resize);
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }
}

frappe.provide("frappe.ui");
frappe.ui.Whiteboard = Whiteboard;

export default Whiteboard;
