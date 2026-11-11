import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Chat from '../src/pages/Chat.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), send: vi.fn(), route: {} }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({}) }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
// Happy DOM does not provide the same DOM traversal as a browser for DOMPurify.
vi.mock('dompurify', () => ({
  default: {
    sanitize: (html, options) => {
      if (!options?.RETURN_DOM_FRAGMENT) return html
      const template = document.createElement('template')
      template.innerHTML = html
      return template.content
    },
  },
}))
vi.mock('../src/lib/mobileBoot', () => ({
  useMobileBoot: () => ({
    loadMobileBoot: async () => {},
    defaultWorkspace: ref('Operations'),
    periBotName: ref('PERI'),
    user: ref('worker@example.test'),
    userFullname: ref('Worker'),
  }),
}))

const channelId = 'peri-chat'
const promptId = 'prompt-1'
const makeMessage = (name, text, fields = {}) => ({
  name, text, channel_id: channelId, creation: '2026-11-11 06:00:00',
  owner: 'worker@example.test', ...fields,
})
const botReply = (text, id = channelId) => makeMessage('reply-1', text, {
  channel_id: id, bot: 'PERI', is_bot_message: 1, creation: '2026-11-11 06:01:00',
})

let wrapper
let history
let threadHistory
let listeners

beforeEach(() => {
  vi.resetAllMocks()
  mocks.route = reactive({
    path: '/chat/peri', fullPath: '/chat/peri', query: { channel: channelId, mode: 'ai' }, meta: {},
  })
  history = []
  threadHistory = []
  listeners = new Map()
  window.frappe = { realtime: {
    on: (event, listener) => listeners.set(event, listener),
    off: (event) => listeners.delete(event),
    isConnected: () => true,
    emit: vi.fn(),
  } }
  mocks.api.mockImplementation(async (url, options) => {
    if (url.includes('get_mobile_chat_bootstrap')) {
      return { message: { current_user: 'worker@example.test', channels: [{ name: channelId }] } }
    }
    if (url.includes('chat_stream.get_messages')) {
      return { message: { messages: url.includes('channel_id=prompt-1') ? threadHistory : history } }
    }
    if (url.includes('get_newer_messages')) return { message: { messages: [] } }
    if (url.includes('get_thread_counts')) return { message: {} }
    if (url.includes('send_message')) return mocks.send(options.body.get('channel_id'))
    throw new Error(`Unexpected API call: ${url}`)
  })
  mocks.send.mockImplementation(async (id) => ({
    message: id === channelId
      ? makeMessage(promptId, 'Analyse the dashboard', { is_thread: 1 })
      : makeMessage('follow-up', 'What are the priorities?', { channel_id: id }),
  }))
})

afterEach(() => {
  wrapper?.unmount()
  delete window.frappe
})

async function openChat() {
  wrapper = mount(Chat, { global: { stubs: {
    MobileSheet: { props: ['open'], template: '<section v-if="open" class="sheet"><slot /></section>' },
  } } })
  await flushPromises()
}

async function sendPrompt(view = wrapper) {
  await view.get('textarea').setValue('Analyse the dashboard')
  await view.get('form').trigger('submit')
  await flushPromises()
}

async function emit(event, data) {
  listeners.get(event)(data)
  await flushPromises()
}

describe('Verto Mobile chat', () => {
  it('renders saved Markdown, escaped quotes, tables, and fenced code', async () => {
    history = [botReply([
      '### Toolbox / Pre-Start Message',
      '- Review the **Hot Works CCV** result',
      '- Check fire watch arrangements',
      '',
      '&gt; Verify the current JHA before work starts.',
      '',
      '| Control | Status |',
      '| --- | --- |',
      '| Fire watch | Verified |',
      '',
      '```html',
      '<p>Example</p>',
      '```',
    ].join('\n'))]
    await openChat()

    const body = wrapper.get('.rich-message-html')
    expect(body.get('h3').text()).toBe('Toolbox / Pre-Start Message')
    expect(body.findAll('ul > li')).toHaveLength(2)
    expect(body.get('strong').text()).toBe('Hot Works CCV')
    expect(body.get('blockquote').text()).toBe('Verify the current JHA before work starts.')
    expect(body.findAll('tbody td').map((cell) => cell.text())).toEqual(['Fire watch', 'Verified'])
    expect(body.get('pre code').text()).toBe('<p>Example</p>')
  })

  it('keeps rich HTML and ordinary line breaks readable', async () => {
    history = [
      makeMessage('html', '<p>Use <strong>the procedure</strong> &lt;draft&gt;.</p>', { content: 'Use the procedure.' }),
      makeMessage('plain', 'First line\nSecond line'),
    ]
    await openChat()

    const [html, plain] = wrapper.findAll('.rich-message-html')
    expect(html.get('strong').text()).toBe('the procedure')
    expect(html.text()).toContain('<draft>')
    expect(plain.get('br').exists()).toBe(true)
  })

  it('shows three dots for the active PERI channel and clears them on Raven completion', async () => {
    await openChat()
    await emit('ai_event', { channel_id: 'another-channel' })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    await emit('ai_event', { channel_id: channelId })
    expect(wrapper.get('[role="status"]').text()).toBe('PERI is thinking')
    expect(wrapper.findAll('.thinking-dot')).toHaveLength(3)
    await emit('ai_event_clear', { channel_id: channelId })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('shows the dots after sending without a live start event and clears them on a thread reply', async () => {
    await openChat()
    await sendPrompt()
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    await emit('thread_reply', { channel_id: 'unrelated-thread', number_of_replies: 1 })
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    await emit('thread_reply', { channel_id: promptId, number_of_replies: 1 })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('shows progress in an open PERI thread and formats the incoming reply', async () => {
    history = [makeMessage(promptId, 'Analyse the dashboard', { is_thread: 1 })]
    await openChat()
    await emit('ai_thread_created', { channel_id: channelId, thread_id: promptId })
    await wrapper.findAll('button').find((button) => button.text() === 'Open thread').trigger('click')
    await flushPromises()

    const thread = wrapper.get('.sheet')
    expect(thread.get('[role="status"]').text()).toBe('PERI is thinking')
    await emit('message_created', { channel_id: promptId, message: botReply('### Thread result', promptId) })
    expect(thread.find('[role="status"]').exists()).toBe(false)
    expect(thread.get('.rich-message-html h3').text()).toBe('Thread result')

    await sendPrompt(thread)
    expect(thread.get('[role="status"]').text()).toBe('PERI is thinking')
    await emit('ai_event_clear', { channel_id: promptId })
    expect(thread.find('[role="status"]').exists()).toBe(false)
  })

  it('keeps showing progress while another PERI thread is still waiting', async () => {
    mocks.send
      .mockResolvedValueOnce({ message: makeMessage(promptId, 'First prompt') })
      .mockResolvedValueOnce({ message: makeMessage('prompt-2', 'Second prompt') })
    await openChat()
    await sendPrompt()
    await sendPrompt()
    await emit('thread_reply', { channel_id: 'prompt-2', number_of_replies: 1 })
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    await emit('thread_reply', { channel_id: promptId, number_of_replies: 1 })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('does not restore a finished indicator when the send returns after a fast reply', async () => {
    let finishSend
    mocks.send.mockReturnValue(new Promise((resolve) => { finishSend = resolve }))
    await openChat()
    await sendPrompt()
    await emit('message_created', { channel_id: channelId, message: botReply('Already answered') })
    finishSend({ message: makeMessage(promptId, 'Analyse the dashboard') })
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('keeps the indicator out of regular chat', async () => {
    mocks.route.path = '/chat'
    delete mocks.route.query.mode
    await openChat()
    await sendPrompt()
    await emit('ai_event', { channel_id: channelId })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })
})
