// Explicit, local-only snapshot. Do not collect page contents, URLs or identity.
export function captureLayoutDiagnostics() {
  const root = document.documentElement
  const viewport = window.visualViewport
  const boxes: Record<string, unknown> = {}
  for (const selector of ['html', 'body', '#app', '.mobile-shell', '.mobile-shell-frame', '.mobile-shell-main', '.bottom-tabs', 'iframe']) {
    const element = document.querySelector(selector)
    if (!element) continue
    const rect = element.getBoundingClientRect()
    const style = getComputedStyle(element)
    boxes[selector] = {
      rect: { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, width: rect.width, height: rect.height },
      position: style.position, height: style.height, minHeight: style.minHeight,
      overflow: style.overflow, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom,
      scrollHeight: element.scrollHeight, clientHeight: element.clientHeight,
    }
  }
  const probe = document.createElement('div')
  probe.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)'
  let safeArea
  const viewportUnits: Record<string, number | null> = {}
  document.body.appendChild(probe)
  try {
    const style = getComputedStyle(probe)
    safeArea = { top: style.paddingTop, bottom: style.paddingBottom }
    for (const unit of ['vh', 'dvh', 'lvh', 'svh']) {
      probe.style.height = ''
      probe.style.height = `100${unit}`
      viewportUnits[unit] = probe.style.height ? parseFloat(getComputedStyle(probe).height) : null
    }
  } finally { probe.remove() }
  const style = getComputedStyle(root)
  return {
    capturedAt: new Date().toISOString(),
    userAgent: navigator.userAgent,
    standalone: (navigator as Navigator & { standalone?: boolean }).standalone === true,
    displayMode: ['standalone', 'fullscreen', 'browser'].filter(mode => window.matchMedia(`(display-mode: ${mode})`).matches),
    flowActive: root.classList.contains('verto-flow-active'),
    screen: { width: screen.width, height: screen.height, availWidth: screen.availWidth, availHeight: screen.availHeight },
    window: { innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio, scrollX, scrollY },
    visualViewport: viewport ? { width: viewport.width, height: viewport.height, offsetTop: viewport.offsetTop, offsetLeft: viewport.offsetLeft, pageTop: viewport.pageTop, scale: viewport.scale } : null,
    viewportMeta: document.querySelector('meta[name="viewport"]')?.getAttribute('content'),
    statusBar: document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')?.getAttribute('content'),
    safeArea,
    viewportUnits,
    cssViewportHeight: style.getPropertyValue('--verto-viewport-height').trim(),
    cssViewportTop: style.getPropertyValue('--verto-viewport-top').trim(),
    boxes,
  }
}
