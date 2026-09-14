import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { Combobox, Select, Checkbox, BottomSheet } from 'frappe-ui'
import { Editor } from 'frappe-ui/editor'
import LinkField from '../src/components/mobile-fields/LinkField.vue'
import RichTextEditorField from '../src/components/mobile-fields/RichTextEditorField.vue'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import MobileSheet from '../src/components/MobileSheet.vue'
const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  cache: vi.fn(),
  merge: vi.fn(),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/pwa/offlineQueue', () => ({
  getCachedLinkOptions: mocks.cache,
  mergeCachedLinkOptions: mocks.merge,
}))
let wrappers = []
const render = (component, options = {}) => {
  const w = mount(component, { attachTo: document.body, ...options })
  wrappers.push(w)
  return w
}
const waitSearch = async () => {
  await new Promise((r) => setTimeout(r, 280))
  await flushPromises()
}
const clickText = async (text) => {
  const el = [...document.querySelectorAll('button')].find(
    (el) => el.textContent.trim() === text
  )
  expect(el, `button ${text}`).toBeTruthy()
  el.click()
  await flushPromises()
}
beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(navigator, 'onLine', {
    configurable: true,
    value: true,
  })
  mocks.api.mockResolvedValue({
    message: [{ name: 'PROJ-1', description: 'Shutdown' }],
  })
  mocks.cache.mockResolvedValue([{ name: 'CACHED-1' }])
  mocks.merge.mockResolvedValue(undefined)
  vi.spyOn(window, 'alert').mockImplementation(() => {})
})
afterEach(() => {
  wrappers.forEach((w) => w.unmount())
  wrappers = []
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})
describe('Link selection with offline cache', () => {
  const field = {
    fieldname: 'project',
    label: 'Project',
    fieldtype: 'Link',
    options: 'Project',
  }
  it('commits a selected ID, preserves saved values, and clears explicitly', async () => {
    const w = render(LinkField, { props: { field, modelValue: 'SAVED-1' } })
    const control = w.findComponent(Combobox)
    expect(control.props('options')[0].value).toBe('SAVED-1')
    control.vm.$emit('update:query', 'Shutdown')
    await waitSearch()
    expect(w.emitted('update:modelValue')).toBeUndefined()
    expect(mocks.api.mock.calls[0][0]).toContain('txt=Shutdown')
    control.vm.$emit('update:modelValue', 'PROJ-1')
    await nextTick()
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['PROJ-1'])
    control.vm.$emit('update:modelValue', null)
    await nextTick()
    expect(w.emitted('update:modelValue').at(-1)).toEqual([''])
    expect(w.emitted('change')).toHaveLength(2)
  })
  it('selects a result using the real popup', async () => {
    const w = render(LinkField, { props: { field } })
    await w.find('input').trigger('click')
    await waitSearch()
    const row = [...document.querySelectorAll('[role="option"]')].find((el) =>
      el.textContent.includes('PROJ-1')
    )
    expect(row).toBeTruthy()
    row.click()
    await flushPromises()
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['PROJ-1'])
  })
  it('uses cached options offline without issuing a server request', async () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: false,
    })
    const w = render(LinkField, { props: { field } })
    w.findComponent(Combobox).vm.$emit('update:query', 'CACHED')
    await waitSearch()
    expect(mocks.api).not.toHaveBeenCalled()
    expect(mocks.cache).toHaveBeenCalledWith('Project', 'CACHED')
    expect(w.findComponent(Combobox).props('options')[0].value).toBe('CACHED-1')
  })
  it('falls back to cached records after network failure', async () => {
    mocks.api.mockRejectedValue(new Error('Network failed'))
    const w = render(LinkField, { props: { field } })
    w.findComponent(Combobox).vm.$emit('update:open', true)
    await waitSearch()
    expect(w.findComponent(Combobox).props('options')[0].value).toBe('CACHED-1')
    expect(w.findComponent(Combobox).props('loading')).toBe(false)
  })
  it('rejects stale responses when the link doctype changes', async () => {
    let finish
    mocks.api.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const w = render(LinkField, { props: { field } })
    w.findComponent(Combobox).vm.$emit('update:query', 'old')
    await waitSearch()
    await w.setProps({ field: { ...field, options: 'Task' } })
    finish({ message: [{ name: 'STALE' }] })
    await flushPromises()
    expect(w.findComponent(Combobox).props('options')).toEqual([])
    await waitSearch()
    expect(mocks.api.mock.calls.at(-1)[0]).toContain('doctype=Task')
  })
  it('does not query when read-only', async () => {
    const w = render(LinkField, {
      props: { field, disabled: true, modelValue: 'SAVED' },
    })
    w.findComponent(Combobox).vm.$emit('update:query', 'test')
    await waitSearch()
    expect(mocks.api).not.toHaveBeenCalled()
    expect(w.find('input').attributes('disabled')).toBeDefined()
  })
})
describe('Rich text HTML round trip', () => {
  it('loads saved HTML and emits formatted edits', async () => {
    const w = render(RichTextEditorField, {
      props: {
        label: 'Work summary',
        modelValue: '<p><strong>Existing</strong></p>',
      },
    })
    await flushPromises()
    expect(w.find('.tiptap').html()).toContain('<strong>Existing</strong>')
    w.findComponent(Editor).vm.editor.commands.setContent(
      '<p><em>Updated</em></p>',
      { emitUpdate: true }
    )
    await flushPromises()
    expect(w.emitted('update:modelValue').at(-1)[0]).toContain(
      '<em>Updated</em>'
    )
  })
  it('normalises empty HTML and respects read-only changes', async () => {
    const w = render(RichTextEditorField, {
      props: { modelValue: '<p>Text</p>' },
    })
    await flushPromises()
    w.findComponent(Editor).vm.editor.commands.clearContent(true)
    await flushPromises()
    expect(w.emitted('update:modelValue').at(-1)).toEqual([''])
    await w.setProps({ disabled: true })
    expect(w.find('.tiptap').attributes('contenteditable')).toBe('false')
    expect(w.find('[data-slot="fixed-menu"]').exists()).toBe(false)
  })
})
describe('Child row editing with v1 controls', () => {
  const field = {
    fieldname: 'rows',
    label: 'Handover rows',
    fieldtype: 'Table',
    child_fields: [
      {
        fieldname: 'summary',
        label: 'Summary',
        fieldtype: 'Data',
        required: true,
      },
      {
        fieldname: 'status',
        label: 'Status',
        fieldtype: 'Select',
        options: 'Open\nClosed',
      },
      { fieldname: 'complete', label: 'Complete', fieldtype: 'Check' },
    ],
  }
  it('adds a row with a selected value and checkbox, preserving existing rows', async () => {
    const w = render(ChildTableField, {
      props: { field, modelValue: [{ summary: 'Existing' }] },
    })
    await clickText('+ Add')
    const input = document.querySelector('input[type="text"]')
    input.value = 'New row'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    w.findComponent(Select).vm.$emit('update:modelValue', 'Closed')
    await w.findComponent(Checkbox).find('input').setValue(true)
    await clickText('Save Row')
    const rows = w.emitted('update:modelValue').at(-1)[0]
    expect(rows).toHaveLength(2)
    expect(rows[0].summary).toBe('Existing')
    expect(rows[1]).toMatchObject({
      summary: 'New row',
      status: 'Closed',
      complete: true,
    })
  })
  it('cancels an unsaved row without changing the table', async () => {
    const w = render(ChildTableField, { props: { field, modelValue: [] } })
    await clickText('+ Add')
    await clickText('Close')
    expect(w.emitted('update:modelValue')).toBeUndefined()
    expect(w.findComponent(MobileSheet).props('open')).toBe(false)
  })
  it('supports keyboard selection inside a sheet without closing the editor', async () => {
    const w = render(ChildTableField, { props: { field, modelValue: [] } })
    await clickText('+ Add')
    const select = w.findComponent(Select)
    await select
      .find('[role="combobox"]')
      .trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()
    const option = [...document.querySelectorAll('[role="option"]')].find(
      (el) => el.textContent.includes('Closed')
    )
    expect(option).toBeTruthy()
    option.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    )
    await flushPromises()
    expect(w.findComponent(MobileSheet).props('open')).toBe(true)
    expect(select.props('modelValue')).toBe('Closed')
  })
  it('opens existing rows read-only and hides mutation actions', async () => {
    const w = render(ChildTableField, {
      props: {
        field,
        disabled: true,
        modelValue: [{ summary: 'Existing', status: 'Open' }],
      },
    })
    await w.find('button').trigger('click')
    await flushPromises()
    expect(w.findComponent(Select).props('disabled')).toBe(true)
    expect(
      [...document.querySelectorAll('button')].some((b) =>
        b.textContent.includes('Save Row')
      )
    ).toBe(false)
  })
})
describe('Mobile sheet focus', () => {
  it('supplies accessible labels and forwards dismissal', async () => {
    const w = render(MobileSheet, {
      props: { open: true, title: 'Project Tools' },
      slots: { default: '<button>Close</button>' },
    })
    await flushPromises()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).toBeTruthy()
    expect(
      document.getElementById(dialog.getAttribute('aria-labelledby'))
        .textContent
    ).toBe('Project Tools')
    expect(dialog.contains(document.activeElement)).toBe(true)
    w.findComponent(BottomSheet).vm.$emit('update:open', false)
    await nextTick()
    expect(w.emitted('update:open')).toEqual([[false]])
  })
})
