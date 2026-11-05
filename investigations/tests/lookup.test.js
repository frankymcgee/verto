import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { Combobox } from 'frappe-ui'
import { flushPromises, mount } from '@vue/test-utils'
import LookupField from '../src/components/LookupField.vue'
import { call } from '../src/api'

vi.mock('../src/api', () => ({ call: vi.fn() }))
let wrapper
beforeEach(() => {
  vi.useFakeTimers()
  call.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  document.body.innerHTML = ''
})
function open(props = {}) {
  wrapper = mount(LookupField, {
    attachTo: document.body,
    props: { label: 'Source incident', kind: 'sources', sourceDoctype: 'EHS Incident', ...props },
  })
  return wrapper.getComponent(Combobox)
}
async function search(box, query) {
  box.vm.$emit('update:open', true)
  box.vm.$emit('update:query', query)
  await nextTick()
  await vi.advanceTimersByTimeAsync(250)
  await flushPromises()
}
describe('permission-filtered investigation lookups', () => {
  it('shows server-ranked results even when their label differs from the search text', async () => {
    call.mockResolvedValue([{ name: 'INC-002', label: 'Coupling movement' }])
    const box = open()
    await search(box, 'client-reference-123')
    expect(call).toHaveBeenCalledWith('search_options', {
      kind: 'sources',
      query: 'client-reference-123',
      source_doctype: 'EHS Incident',
    })
    expect(document.body.textContent).toContain('Coupling movement')
  })
  it('ignores an older search response after a newer search has completed', async () => {
    let resolveOld
    call.mockImplementation((method, params) =>
      params.query === 'old'
        ? new Promise((resolve) => {
            resolveOld = resolve
          })
        : Promise.resolve([{ name: 'INC-NEW', label: 'Current accessible incident' }]),
    )
    const box = open()
    await search(box, 'old')
    await search(box, 'new')
    resolveOld([{ name: 'INC-OLD', label: 'Stale incident' }])
    await flushPromises()
    expect(document.body.textContent).toContain('Current accessible incident')
    expect(document.body.textContent).not.toContain('Stale incident')
  })
  it('does not request new options when the investigation field is disabled', async () => {
    const box = open({ modelValue: 'INC-RETAINED', disabled: true })
    await search(box, 'other incident')
    expect(call).not.toHaveBeenCalled()
    expect(wrapper.get('input').element.disabled).toBe(true)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
