import { config } from '@vue/test-utils'
import { Button } from 'frappe-ui'
config.global.components = { Button }
// Browser APIs used by accessible Reka controls, absent in DOM simulation.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof Element !== 'undefined') {
  Element.prototype.scrollIntoView ??= function () {}
  Element.prototype.hasPointerCapture ??= function () {
    return false
  }
  Element.prototype.setPointerCapture ??= function () {}
  Element.prototype.releasePointerCapture ??= function () {}
}
