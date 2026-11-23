import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { inject } from 'vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), raven: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/pages/Chat.vue', () => ({ default: {
  setup() { mocks.raven() }, template: '<div class="raven-chat">Raven chat</div>',
} }))

let wrapper
let settings
beforeEach(() => {
  vi.resetModules()
  vi.resetAllMocks()
  sessionStorage.clear()
  settings = { user: 'worker@example.test', peri_chat_version: 'Flow', peri_flow_agent: 'PERI' }
  mocks.api.mockImplementation(async url => {
    if (url.endsWith('get_mobile_boot')) return { message: settings }
    if (url.endsWith('open_peri_chat')) return { message: { url: '/flow/s/test-session', session: 'test-session' } }
    if (url.endsWith('frappe.flow.api.run')) return { message: { run: 'run-1', status: 'started' } }
    if (url.endsWith('get_or_create_peri_channel')) return { message: { channel_id: 'raven-peri' } }
    throw new Error(`Unexpected API: ${url}`)
  })
})
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals() })

async function navigation(project) {
  const { preparePeriChatRoute } = await import('../src/lib/periChat')
  return preparePeriChatRoute(project)
}

async function open(route = '/chat/peri', component = 'AskPeri') {
  const page = (await import(`../src/pages/${component}.vue`)).default
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/chat/peri', component: page },
  ] })
  await router.push(route)
  await router.isReady()
  wrapper = mount(page, { global: { plugins: [router] } })
  await vi.dynamicImportSettled()
  await flushPromises()
  await flushPromises()
  return router
}

describe('Ask PERI backend selection', () => {
  it('opens native Flow inline and never initialises Raven or opens a window', async () => {
    const popup = vi.spyOn(window, 'open')
    await open()
    expect(wrapper.get('iframe').attributes('src')).toBe('/flow/s/test-session')
    expect(wrapper.get('iframe').attributes('title')).toContain('PERI')
    expect(wrapper.find('.app-browser-drawer').exists()).toBe(false)
    expect(mocks.raven).not.toHaveBeenCalled()
    expect(mocks.api.mock.calls.some(([url]) => url.includes('raven'))).toBe(false)
    expect(popup).not.toHaveBeenCalled()
    popup.mockRestore()
  })

  it('retains Raven for existing sites without a version setting', async () => {
    delete settings.peri_chat_version
    await open()
    expect(wrapper.find('.raven-chat').exists()).toBe(true)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(mocks.api.mock.calls.some(([url]) => url.includes('open_peri_chat'))).toBe(false)
  })

  it('waits for settings before mounting either backend', async () => {
    let resolve
    mocks.api.mockImplementation(() => new Promise(r => { resolve = r }))
    await open()
    expect(wrapper.text()).toContain('Loading Ask PERI')
    expect(mocks.raven).not.toHaveBeenCalled()
    mocks.api.mockResolvedValue({ message: { url: '/flow/s/test-session', session: 'test-session' } })
    resolve({ message: settings })
    await vi.dynamicImportSettled(); await flushPromises()
    expect(wrapper.find('iframe').exists()).toBe(true)
    expect(mocks.raven).not.toHaveBeenCalled()
  })

  it('shows a boot failure with retry instead of starting Raven with defaults', async () => {
    mocks.api.mockRejectedValueOnce(new Error('Settings unavailable'))
    await open()
    expect(wrapper.get('[role="alert"]').text()).toContain('Settings unavailable')
    expect(mocks.raven).not.toHaveBeenCalled()
    await wrapper.get('button').trigger('click'); await vi.dynamicImportSettled(); await flushPromises()
    expect(wrapper.find('iframe').exists()).toBe(true)
  })
})

describe('PERI navigation and project analysis', () => {
  it('routes to Flow without resolving a Raven channel and clears stale Raven prompts', async () => {
    sessionStorage.setItem('verto_peri_autosend_message', 'Old Raven prompt')
    expect(await navigation()).toEqual({ path: '/chat/peri', query: { mode: 'ai' } })
    expect(mocks.api).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('verto_peri_autosend_message')).toBeNull()
  })

  it('keeps the Raven channel and project autosend behaviour when selected', async () => {
    settings.peri_chat_version = 'Raven'
    expect(await navigation('SPT2603 | PORT MAJOR')).toEqual({ path: '/chat/peri', query: {
      channel: 'raven-peri', mode: 'ai', auto: 'analyse',
    } })
    expect(sessionStorage.getItem('verto_peri_autosend_message')).toBe('Analyse the dashboard for SPT2603 | PORT MAJOR')
  })

  it('starts a fresh Flow conversation and sends the project prompt exactly once', async () => {
    const target = await navigation('SPT2603 | PORT MAJOR')
    await open(target)
    const calls = mocks.api.mock.calls
    expect(calls.find(([url]) => url.endsWith('open_peri_chat'))[1].body.get('new_chat')).toBe('1')
    const runs = calls.filter(([url]) => url.endsWith('frappe.flow.api.run'))
    expect(runs).toHaveLength(1)
    expect(runs[0][1].method).toBe('POST')
    expect(runs[0][1].body.get('session')).toBe('test-session')
    expect(runs[0][1].body.get('message')).toBe('Analyse the dashboard for SPT2603 | PORT MAJOR')
    wrapper.unmount(); wrapper = undefined
    await open(target)
    expect(mocks.api.mock.calls.filter(([url]) => url.endsWith('frappe.flow.api.run'))).toHaveLength(1)
  })

  it('does not replay a prompt queued by a different account', async () => {
    const target = await navigation('Private project')
    const { useMobileBoot } = await import('../src/lib/mobileBoot')
    settings = { ...settings, user: 'other@example.test' }
    await useMobileBoot().reloadMobileBoot()
    await open(target)
    expect(mocks.api.mock.calls.some(([url]) => url.endsWith('frappe.flow.api.run'))).toBe(false)
  })

  it('does not send the queued prompt after navigating away during session creation', async () => {
    const target = await navigation('Project')
    let resolve
    mocks.api.mockImplementation(url => url.endsWith('open_peri_chat')
      ? new Promise(r => { resolve = r }) : Promise.resolve({ message: settings }))
    await open(target)
    wrapper.unmount(); wrapper = undefined
    resolve({ message: { url: '/flow/s/test-session', session: 'test-session' } })
    await flushPromises()
    expect(mocks.api.mock.calls.some(([url]) => url.endsWith('frappe.flow.api.run'))).toBe(false)
  })
})

describe('Flow errors and recall', () => {
  it('shows access errors inline and retries without opening another surface', async () => {
    await navigation()
    mocks.api.mockRejectedValueOnce(new Error('Flow Agent access denied'))
    await open()
    expect(wrapper.get('[role="alert"]').text()).toContain('Flow Agent access denied')
    expect(wrapper.find('iframe').exists()).toBe(false)
    await wrapper.get('button').trigger('click'); await flushPromises()
    expect(wrapper.find('iframe').exists()).toBe(true)
  })

  it('can recover from an unusable remembered conversation by starting a new one', async () => {
    await navigation()
    mocks.api.mockRejectedValueOnce(new Error('This PERI conversation belongs to another user.'))
    await open()
    const button = wrapper.findAll('button').find(b => b.text() === 'Start a new PERI chat')
    await button.trigger('click'); await flushPromises()
    const calls = mocks.api.mock.calls.filter(([url]) => url.endsWith('open_peri_chat'))
    expect(calls.at(-1)[1].body.get('new_chat')).toBe('1')
    expect(wrapper.find('iframe').exists()).toBe(true)
  })

  it('rejects external iframe URLs', async () => {
    await navigation()
    mocks.api.mockResolvedValueOnce({ message: { url: 'https://other.test/flow/s/chat', session: 'chat' } })
    await open()
    expect(wrapper.get('[role="alert"]').text()).toContain('invalid conversation URL')
    expect(wrapper.find('iframe').exists()).toBe(false)
  })

  it('opens the conversation after an ambiguous run error and does not resend on reload', async () => {
    const target = await navigation('Project')
    mocks.api.mockImplementation(async url => {
      if (url.endsWith('open_peri_chat')) return { message: { url: '/flow/s/test-session', session: 'test-session' } }
      if (url.endsWith('frappe.flow.api.run')) throw new Error('Connection lost')
      return { message: settings }
    })
    await open(target)
    expect(wrapper.get('[role="alert"]').text()).toContain('Check the conversation before sending')
    expect(wrapper.find('iframe').exists()).toBe(true)
    wrapper.unmount(); wrapper = undefined
    await open(target)
    expect(mocks.api.mock.calls.filter(([url]) => url.endsWith('frappe.flow.api.run'))).toHaveLength(1)
  })

  it('recalls conversations using a user and agent scoped storage key', async () => {
    sessionStorage.setItem('verto:peri:flow-session:worker@example.test:PERI', 'my-chat')
    await open()
    const call = mocks.api.mock.calls.find(([url]) => url.endsWith('open_peri_chat'))
    expect(call[1].body.get('session')).toBe('my-chat')
    expect(sessionStorage.getItem('verto:peri:flow-session:worker@example.test:PERI')).toBe('test-session')
  })
})

describe('Embedded Flow viewport sizing', () => {
  it.each(['browser', 'ios-browser', 'ios-standalone'])(
    'resizes with the keyboard and restores the normal shell on leaving Flow (%s)', async mode => {
    const ios = mode.startsWith('ios')
    const userAgent = vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(ios ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X)' : 'Desktop test browser')
    const standalone = Object.getOwnPropertyDescriptor(navigator, 'standalone')
    Object.defineProperty(navigator, 'standalone', { configurable: true, value: mode === 'ios-standalone' })
    await navigation()
    const viewport = new EventTarget()
    viewport.height = 844
    viewport.scale = 1
    viewport.offsetTop = 0
    const original = Object.getOwnPropertyDescriptor(window, 'visualViewport')
    Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport })
    try {
      const shell = (await import('../src/layouts/MobileShell.vue')).default
      const { flowEditingKey } = await import('../src/lib/flowFrame')
      const router = createRouter({ history: createMemoryHistory(), routes: [
        { path: '/chat/peri', component: {
          setup() { return { setEditing: inject(flowEditingKey) } },
          template: '<textarea @focus="setEditing(true)" @blur="setEditing(false)" />',
        } },
        { path: '/', component: { template: '<div>Home</div>' } },
      ] })
      await router.push('/chat/peri'); await router.isReady()
      wrapper = mount(shell, { global: { plugins: [router], stubs: {
        AppHeader: true, BottomTabs: true, AppBrowserDrawer: true, OfflineSyncStatus: true,
        MissingHoursReminder: true, PwaUpdatePrompt: true, PwaInstallPrompt: true,
      } } })
      await flushPromises()
      expect(document.documentElement.classList.contains('verto-flow-active')).toBe(true)
      expect(document.documentElement.classList.contains('verto-flow-standalone-ios')).toBe(mode === 'ios-standalone')
      // At rest, Flow fills CSS's dynamic viewport rather than leaving a gap
      // when Safari's visual viewport differs from its browser-toolbar layout.
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
      viewport.height = 800
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
      await wrapper.get('textarea').trigger('focus')
      viewport.height = 480
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('480px')
      expect(document.documentElement.style.getPropertyValue('--verto-flow-footer-safe-bottom')).toBe('0px')
      viewport.offsetTop = 168
      viewport.dispatchEvent(new Event('scroll'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-top')).toBe('168px')
      // Pinching must not squeeze the full app into the zoomed visual viewport.
      viewport.scale = 2
      viewport.height = 240
      viewport.offsetTop = 300
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('480px')
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-top')).toBe('168px')
      viewport.scale = 1
      viewport.height = 844
      viewport.offsetTop = 0
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
      expect(document.documentElement.style.getPropertyValue('--verto-flow-footer-safe-bottom')).toBe('')
      await wrapper.get('textarea').trigger('blur')
      viewport.height = 600
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
      await router.push('/'); await flushPromises()
      expect(document.documentElement.classList.contains('verto-flow-active')).toBe(false)
      expect(document.documentElement.classList.contains('verto-flow-standalone-ios')).toBe(false)
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-top')).toBe('')
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
      viewport.height = 600
      viewport.dispatchEvent(new Event('resize'))
      expect(document.documentElement.style.getPropertyValue('--verto-viewport-height')).toBe('')
    } finally {
      wrapper?.unmount(); wrapper = undefined
      expect(document.documentElement.classList.contains('verto-flow-standalone-ios')).toBe(false)
      userAgent.mockRestore()
      if (standalone) Object.defineProperty(navigator, 'standalone', standalone)
      else delete navigator.standalone
      if (original) Object.defineProperty(window, 'visualViewport', original)
      else delete window.visualViewport
    }
  })
})

describe('Flow iframe and shadow DOM integration', () => {
  let dispose, doc
  afterEach(() => {
    dispose?.(); dispose = undefined
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-theme-mode')
  })

  async function attachStyles() {
    const { installEmbeddedFlowStyles } = await import('../src/lib/flowFrame')
    doc = document.implementation.createHTMLDocument('Flow')
    dispose = installEmbeddedFlowStyles(doc)
  }

  it('reports editing in a shadow composer and clears it on blur and cleanup', async () => {
    const { installEmbeddedFlowStyles } = await import('../src/lib/flowFrame')
    const editing = vi.fn()
    const host = document.createElement('div')
    document.body.append(host)
    const shadow = host.attachShadow({ mode: 'open' })
    shadow.innerHTML = '<textarea></textarea>'
    try {
      dispose = installEmbeddedFlowStyles(document, editing)
      expect(editing).toHaveBeenLastCalledWith(false)
      const field = shadow.querySelector('textarea')
      field.focus(); await flushPromises()
      expect(editing).toHaveBeenLastCalledWith(true)
      field.blur(); await flushPromises()
      expect(editing).toHaveBeenLastCalledWith(false)
      field.focus(); await flushPromises()
      dispose()
      expect(editing).toHaveBeenLastCalledWith(false)
      editing.mockClear()
      field.blur(); field.focus(); await flushPromises()
      expect(editing).not.toHaveBeenCalled()
    } finally { dispose?.(); host.remove() }
  })

  it('raises a phone shadow editor and its formatted text to 16px without changing viewport zoom', async () => {
    const { installEmbeddedFlowStyles } = await import('../src/lib/flowFrame')
    const size = { width: window.innerWidth, height: window.innerHeight }
    const host = document.createElement('div')
    document.body.append(host)
    const root = host.attachShadow({ mode: 'open' })
    root.innerHTML = '<style>.editor { font-size: 14px } .editor span { font-size: 12px }</style><div contenteditable="true" class="editor"><span>Draft</span></div>'
    window.happyDOM.setWindowSize({ width: 390, height: 844 })
    try {
      const editor = root.querySelector('.editor')
      expect(getComputedStyle(editor).fontSize).toBe('14px')
      const viewport = document.querySelector('meta[name="viewport"]')?.content
      dispose = installEmbeddedFlowStyles(document)
      await flushPromises()
      expect(getComputedStyle(editor).fontSize).toBe('16px')
      expect(getComputedStyle(editor.querySelector('span')).fontSize).toBe('16px')
      expect(document.querySelector('meta[name="viewport"]')?.content).toBe(viewport)
    } finally {
      dispose?.(); host.remove(); window.happyDOM.setWindowSize(size)
    }
  })

  it('styles an existing shadow composer and newly mounted islands before focusing', async () => {
    await attachStyles()
    const host = doc.createElement('div')
    doc.body.append(host)
    // Flow appends its host, attaches a shadow root, then marks data-panel.
    const root = host.attachShadow({ mode: 'open' })
    root.innerHTML = '<div contenteditable="true"><p>Draft</p></div>'
    host.toggleAttribute('data-panel', false)
    host.setAttribute('data-panel', '')
    await flushPromises()
    const style = root.querySelector('style[data-verto-flow-mobile]')
    expect(style).not.toBeNull()
    expect(style.sheet.cssRules.length).toBeGreaterThan(0)
    root.querySelector('[contenteditable]').replaceWith(doc.createElement('textarea'))
    await flushPromises()
    expect(root.querySelectorAll('style[data-verto-flow-mobile]')).toHaveLength(1)
    dispose()
    expect(root.querySelector('style[data-verto-flow-mobile]')).toBeNull()
    expect(doc.querySelector('style[data-verto-flow-mobile]')).toBeNull()
    const laterHost = doc.createElement('div')
    laterHost.attachShadow({ mode: 'open' })
    doc.body.append(laterHost)
    await flushPromises()
    expect(laterHost.shadowRoot.children).toHaveLength(0)
  })

  it('mirrors the app theme into Flow and corrects a late native theme change', async () => {
    document.documentElement.dataset.theme = 'dark'
    document.documentElement.dataset.themeMode = 'automatic'
    await attachStyles()
    expect(doc.documentElement.dataset.theme).toBe('dark')
    expect(doc.documentElement.style.colorScheme).toBe('dark')
    document.documentElement.dataset.theme = 'light'
    await flushPromises()
    expect(doc.documentElement.dataset.theme).toBe('light')
    doc.documentElement.dataset.theme = 'dark'
    await flushPromises()
    expect(doc.documentElement.dataset.theme).toBe('light')
    dispose()
    document.documentElement.dataset.theme = 'dark'
    await flushPromises()
    expect(doc.documentElement.dataset.theme).toBe('light')
  })
})
