// Browser APIs used by the actual Frappe UI / Reka controls.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Element.prototype.scrollIntoView ??= function () {}
Element.prototype.hasPointerCapture ??= function () {
  return false
}
Element.prototype.setPointerCapture ??= function () {}
Element.prototype.releasePointerCapture ??= function () {}

// Happy DOM 21 omits printing. Tests spy on this inert default.
window.print ??= function () {}
