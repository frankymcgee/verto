import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiRequest } from '../src/lib/api'
import JhaPrintEmail from '../src/components/JhaPrintEmail.vue'
import JhaReviewSignoff from '../src/components/JhaReviewSignoff.vue'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
let wrapper
const jha = { name: 'JHA-1', revision: 2, status: 'Signed' }
const delivery = (status = 'Sent', values = {}) => ({ jha: 'JHA-1', revision: 2, status,
  recipient: 'site@example.test', configured_recipient: 'site@example.test', can_resend: true, ...values })
const button = text => wrapper.findAll('button').find(item => item.text() === text)
beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers(); apiRequest.mockResolvedValue({ message: delivery() }) })
afterEach(() => { wrapper?.unmount(); vi.useRealTimers() })
async function open(value = jha) { wrapper = mount(JhaPrintEmail, { props: { jha: value } }); await flushPromises() }

describe('signed JHA printing email', () => {
  it('shows the delivered revision and destination without an extra crew action', async () => {
    await open()
    expect(wrapper.text()).toContain('Print copy sent')
    expect(wrapper.text()).toContain('site@example.test · Revision 2')
    expect(wrapper.text()).not.toContain('printed successfully')
    expect(apiRequest.mock.calls[0][1]).toEqual({ cache: 'no-store' })
    expect(apiRequest.mock.calls.every(([, options]) => options.method !== 'POST')).toBe(true)
  })
  it('only appears after sign-on and does not send a print email from the screen', async () => {
    await open({ ...jha, status: 'Ready for Team Review' })
    expect(apiRequest).not.toHaveBeenCalled(); expect(wrapper.find('section').exists()).toBe(false)
    await wrapper.setProps({ jha }); await flushPromises()
    expect(wrapper.text()).toContain('Print copy sent'); expect(apiRequest).toHaveBeenCalledTimes(1)
  })
  it('updates pending delivery automatically and stops polling after SMTP reports Sent', async () => {
    apiRequest.mockResolvedValueOnce({ message: delivery('Pending', { can_resend: false }) }).mockResolvedValue({ message: delivery('Sent') })
    await open(); expect(wrapper.text()).toContain('Your signed JHA is saved')
    await vi.advanceTimersByTimeAsync(5000); await flushPromises()
    expect(wrapper.text()).toContain('Print copy sent')
    await vi.advanceTimersByTimeAsync(15000); expect(apiRequest).toHaveBeenCalledTimes(2)
  })
  it('requires supervisor permission and explicit confirmation for another copy', async () => {
    apiRequest.mockResolvedValue({ message: delivery('Failed', { can_resend: false }) }); await open()
    expect(button('Send print copy')).toBeUndefined()
    apiRequest.mockResolvedValue({ message: delivery('Sent') }); await button('Check email status').trigger('click'); await flushPromises()
    await button('Resend print copy').trigger('click')
    expect(button('Email signed PDF').attributes('disabled')).toBeDefined()
    await wrapper.find('input[type=checkbox]').setValue(true)
    apiRequest.mockResolvedValue({ message: delivery('Pending', { can_resend: false }) })
    await wrapper.find('form').trigger('submit'); await flushPromises()
    const [url, options] = apiRequest.mock.calls.at(-1)
    expect(url).toContain('resend_jha_print_email')
    expect(Object.fromEntries(options.body)).toMatchObject({ jha_name: 'JHA-1', confirmation: '1' })
    expect(options.body.get('request_id')).toBeTruthy()
    expect(wrapper.text()).toContain('Sending print copy')
  })
  it('reuses the request ID after a network failure so retrying cannot duplicate an accepted request', async () => {
    await open(); await button('Resend print copy').trigger('click'); await wrapper.find('input').setValue(true)
    apiRequest.mockRejectedValueOnce(Error('Connection lost'))
    await wrapper.find('form').trigger('submit'); await flushPromises()
    const first = apiRequest.mock.calls.at(-1)[1].body.get('request_id')
    apiRequest.mockResolvedValue({ message: delivery('Queued', { can_resend: false }) })
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(apiRequest.mock.calls.at(-1)[1].body.get('request_id')).toBe(first)
  })
  it('ignores stale status after a different JHA opens and cancels polling when leaving', async () => {
    let finish
    apiRequest.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await open()
    apiRequest.mockResolvedValue({ message: delivery('Pending', { jha: 'JHA-2', can_resend: false }) })
    await wrapper.setProps({ jha: { ...jha, name: 'JHA-2' } }); await flushPromises()
    finish({ message: delivery('Sent') }); await flushPromises()
    expect(wrapper.text()).not.toContain('Print copy sent')
    wrapper.unmount(); const calls = apiRequest.mock.calls.length
    await vi.advanceTimersByTimeAsync(60000); expect(apiRequest).toHaveBeenCalledTimes(calls)
  })
  it('shows setup guidance when neither the project nor the default has an address', async () => {
    apiRequest.mockResolvedValue({ message: delivery('Not Configured', { recipient: '', can_resend: false }) }); await open()
    expect(wrapper.text()).toContain('JHA Printing Email on the Project')
    expect(button('Send print copy')).toBeUndefined()
  })
  it('is included on the completed sign-on screen', async () => {
    apiRequest.mockImplementation(async url => ({ message: url.includes('get_jha_review_state')
      ? { ...jha, review_completed: 1, participants: [] } : delivery() }))
    wrapper = mount(JhaReviewSignoff, { props: { jha } }); await flushPromises()
    expect(wrapper.text()).toContain('Human review and participant sign-on complete')
    expect(wrapper.findComponent(JhaPrintEmail).exists()).toBe(true)
    expect(wrapper.text()).toContain('Print copy sent')
  })
})
