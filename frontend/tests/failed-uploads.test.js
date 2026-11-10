import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FailedUploads from '../src/pages/FailedUploads.vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), discard: vi.fn(), sync: vi.fn(), summary: vi.fn(), navigate: vi.fn(), online: true,
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.navigate }) }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ user: ref('worker@example.test') }) }))
vi.mock('../src/pwa/useOfflineSync', () => ({ useOfflineSync: () => ({ isOnline: ref(mocks.online), refreshSummary: mocks.summary }) }))
vi.mock('../src/pwa/offlineQueue', () => ({
  getFailedOfflineQueueItems: mocks.list,
  discardFailedOfflineQueueItem: mocks.discard,
  syncOfflineQueueItem: mocks.sync,
}))

const upload = (extra = {}) => ({
  id: 'batb-1', kind: 'mobile_document', mobile_doctype: 'supervisor-batb',
  created_at: '2026-11-10T00:00:00Z', attempts: 3, status: 'failed',
  last_error: 'A required field is missing: <b>Project</b>', ...extra,
})
let wrapper
const click = async (label) => {
  const button = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === label)
  expect(button).toBeTruthy()
  button.click()
  await flushPromises()
}
const openPage = async () => {
  wrapper = mount(FailedUploads, { attachTo: document.body })
  await flushPromises()
}
beforeEach(() => {
  vi.resetAllMocks()
  mocks.online = true
  mocks.list.mockResolvedValue([upload()])
})
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
})

describe('Failed uploads page', () => {
  it('shows the BATB error as text and preserves the item when removal is cancelled', async () => {
    await openPage()
    expect(mocks.list).toHaveBeenCalledWith('worker@example.test')
    expect(wrapper.text()).toContain('Supervisor BATB')
    expect(wrapper.text()).toContain('A required field is missing: <b>Project</b>')
    expect(wrapper.find('b').exists()).toBe(false)
    await click('Remove upload')
    expect(document.body.textContent).toContain('This cannot be undone.')
    expect(mocks.discard).not.toHaveBeenCalled()
    await click('Cancel')
    expect(mocks.discard).not.toHaveBeenCalled()
  })

  it('removes only the confirmed upload offline and refreshes the queue status', async () => {
    mocks.online = false
    await openPage()
    expect(wrapper.findAll('button').find(button => button.text() === 'Retry upload').attributes('disabled')).toBeDefined()
    await click('Remove upload')
    mocks.list.mockResolvedValue([])
    await click('Remove permanently')
    expect(mocks.discard).toHaveBeenCalledWith('batb-1', 'worker@example.test')
    expect(mocks.sync).not.toHaveBeenCalled()
    expect(mocks.summary).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('No failed uploads')
  })

  it('explains partial success and keeps server documents when discarding pending photos', async () => {
    mocks.list.mockResolvedValue([upload({ server_result: { doctype: 'Supervisor BATB', name: 'BATB-123' } })])
    await openPage()
    expect(wrapper.text()).toContain('BATB-123')
    expect(wrapper.text()).toContain('was saved to the server')
    await click('Remove upload')
    expect(document.body.textContent).toContain('The existing server document and any photos already uploaded will be kept.')
  })

  it('retries the original operation and retains the error when it is rejected again', async () => {
    mocks.sync.mockRejectedValueOnce(new Error('Upload rejected'))
    await openPage()
    await click('Retry upload')
    expect(mocks.sync).toHaveBeenCalledWith('batb-1')
    expect(wrapper.get('[role="alert"]').text()).toBe('Upload rejected')
    expect(wrapper.findAll('article')).toHaveLength(1)
    expect(mocks.discard).not.toHaveBeenCalled()
  })

  it('reports an auto-sync race without claiming the upload was removed', async () => {
    mocks.discard.mockRejectedValueOnce(new Error('This upload is syncing.'))
    await openPage()
    await click('Remove upload')
    await click('Remove permanently')
    expect(wrapper.get('[role="alert"]').text()).toContain('syncing')
    expect(wrapper.text()).not.toContain('removed from failed uploads')
    expect(wrapper.findAll('article')).toHaveLength(1)
  })
})
