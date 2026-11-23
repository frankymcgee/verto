import { afterEach, describe, expect, it, vi } from 'vitest'
import { captureLayoutDiagnostics } from '../src/lib/layoutDiagnostics'

afterEach(() => {
  document.body.innerHTML = ''
  document.documentElement.classList.remove('verto-flow-active')
  vi.restoreAllMocks()
})

describe('local layout diagnostics', () => {
  it('distinguishes the exposed viewport from the screen without collecting page data', () => {
    document.documentElement.classList.add('verto-flow-active')
    document.body.innerHTML = '<div class="mobile-shell"><nav class="bottom-tabs">Private user name</nav><iframe name="private-session"></iframe><textarea>Private conversation</textarea></div>'
    vi.spyOn(window.screen, 'height', 'get').mockReturnValue(956)
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(894)
    vi.spyOn(document.querySelector('.bottom-tabs'), 'getBoundingClientRect').mockReturnValue({ top: 792, bottom: 894, left: 0, right: 440, width: 440, height: 102 })
    const report = captureLayoutDiagnostics()
    expect(report.screen.height - report.window.innerHeight).toBe(62)
    expect(report.boxes['.bottom-tabs'].rect.bottom).toBe(894)
    expect(report.flowActive).toBe(true)
    expect(JSON.stringify(report)).not.toMatch(/Private|private-session/)
    expect(document.body.children).toHaveLength(1)
  })
})
