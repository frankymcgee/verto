// Flow is a same-origin page whose UI is mounted in an open shadow root.
// Verto's normal mobile form styles cannot cross either boundary.
import type { InjectionKey } from 'vue'

export const flowEditingKey: InjectionKey<(editing: boolean) => void> = Symbol('flow-editing')
const TEXT_CONTROL_STYLES = `
  input, textarea, select,
  [contenteditable]:not([contenteditable="false"]), [role="textbox"],
  [contenteditable]:not([contenteditable="false"]) * {
    font-size: 16px !important;
  }
`
const EMBEDDED_STYLES = `
  html, body, #app {
    height: 100%;
    min-height: 0;
    overflow: clip;
    overscroll-behavior: none;
  }
  @media (max-width: 1023px) { ${TEXT_CONTROL_STYLES} }
  @media (pointer: coarse) { ${TEXT_CONTROL_STYLES} }
`

export function installEmbeddedFlowStyles(doc: Document, onEditingChange?: (editing: boolean) => void) {
  const styles = new Map<Document | ShadowRoot, HTMLStyleElement>()
  const observers: MutationObserver[] = []
  let disposed = false
  function reportEditing() {
    if (disposed) return
    let active = doc.activeElement
    while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement
    onEditingChange?.(doc.hasFocus() && Boolean(active?.matches('input, textarea, [role="textbox"], [contenteditable]:not([contenteditable="false"])')))
  }
  const onBlur = () => queueMicrotask(reportEditing)
  doc.addEventListener('focusin', reportEditing, true)
  doc.addEventListener('focusout', onBlur, true)
  doc.defaultView?.addEventListener('focus', reportEditing)
  doc.defaultView?.addEventListener('blur', onBlur)
  reportEditing()
  const parent = document.documentElement
  function syncTheme() {
    const root = doc.documentElement
    const theme = parent.dataset.theme === 'dark' ? 'dark' : 'light'
    const mode = parent.dataset.themeMode || theme
    if (root.dataset.theme !== theme) root.dataset.theme = theme
    if (root.dataset.themeMode !== mode) root.dataset.themeMode = mode
    root.style.colorScheme = theme
  }
  syncTheme()
  // Flow's island already observes its document theme and updates its shadow UI.
  // Also correct a late native mount or system event that reapplies an old mode.
  const themeObserver = new MutationObserver(syncTheme)
  themeObserver.observe(parent, { attributes: true, attributeFilter: ['data-theme', 'data-theme-mode'] })
  themeObserver.observe(doc.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-theme-mode'] })
  observers.push(themeObserver)

  function scan(node: ParentNode) {
    if ('shadowRoot' in node && node.shadowRoot) install(node.shadowRoot as ShadowRoot)
    node.querySelectorAll('*').forEach(element => {
      if (element.shadowRoot) install(element.shadowRoot)
    })
  }

  function install(root: Document | ShadowRoot) {
    if (styles.has(root)) return
    const style = doc.createElement('style')
    style.dataset.vertoFlowMobile = ''
    style.textContent = EMBEDDED_STYLES
    styles.set(root, style)
    // The document handles the frame's root scrolling; each shadow root needs
    // its own copy of the control rules before the first tap (not on focus).
    const target = root === doc ? doc.head : root
    target.appendChild(style)

    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'attributes') scan(record.target as Element)
        record.addedNodes.forEach(node => {
          if (node.nodeType === 1) scan(node as Element)
        })
      }
    })
    observer.observe(root, {
      childList: true, subtree: true,
      // Flow marks its shadow host after its asynchronous island mount.
      attributes: true, attributeFilter: ['data-panel'],
    })
    observers.push(observer)
    scan(root)
  }

  install(doc)
  return () => {
    disposed = true
    doc.removeEventListener('focusin', reportEditing, true)
    doc.removeEventListener('focusout', onBlur, true)
    doc.defaultView?.removeEventListener('focus', reportEditing)
    doc.defaultView?.removeEventListener('blur', onBlur)
    onEditingChange?.(false)
    observers.forEach(observer => observer.disconnect())
    styles.forEach(style => style.remove())
    styles.clear()
  }
}
