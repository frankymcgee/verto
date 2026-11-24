import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { toRaw } from 'vue'
import AttachmentPicker from '../src/components/AttachmentPicker.vue'
import { photoPoint } from '../src/lib/photoAnnotation'

vi.mock('../src/components/PhotoAnnotationEditor.vue', () => ({ __esModule: true, default: { name: 'PhotoAnnotationEditor', props: ['file'], emits: ['close', 'save'], template: '<div>Annotation editor</div>' } }))
let wrapper
let revoke
beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(file => `blob:${file.name}`), revokeObjectURL: vi.fn() }))
  revoke = URL.revokeObjectURL
})
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals(); document.body.innerHTML = '' })
async function choose(files) {
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { configurable: true, value: files })
  await input.trigger('change')
  const selected = wrapper.emitted('update:modelValue').at(-1)[0]
  await wrapper.setProps({ modelValue: selected })
  return selected
}

describe('Photo evidence selection', () => {
  it('adds successive selections and retains the original bytes beside an annotated copy', async () => {
    const original = new File(['original bytes'], 'site.jpg', { type: 'image/jpeg' })
    const document = new File(['report'], 'report.pdf', { type: 'application/pdf' })
    wrapper = mount(AttachmentPicker, { props: { modelValue: [] } })
    await choose([original]); const selected = await choose([document])
    expect(selected).toEqual([original, document])
    expect(wrapper.findAll('button').filter(button => button.text() === 'Annotate')).toHaveLength(1)
    await wrapper.findAll('button').find(button => button.text() === 'Annotate').trigger('click')
    await flushPromises()
    const editor = wrapper.findComponent({ name: 'PhotoAnnotationEditor' })
    expect(toRaw(editor.props('file'))).toBe(original)
    const copy = new File(['marked up'], 'site-annotated.jpg', { type: 'image/jpeg' })
    editor.vm.$emit('save', copy); await flushPromises()
    const saved = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(saved).toEqual([original, document, copy])
    expect(toRaw(saved[0])).toBe(original)
    expect(saved[0].size).toBe('original bytes'.length)
    expect(wrapper.emitted('busy')).toEqual([[true], [false]])
  })

  it('cancels annotation without changing attachments and releases photo previews', async () => {
    const original = new File(['image'], 'site.jpg', { type: 'image/jpeg' })
    wrapper = mount(AttachmentPicker, { props: { modelValue: [original] } })
    await wrapper.findAll('button').find(button => button.text() === 'Annotate').trigger('click')
    await flushPromises()
    wrapper.findComponent({ name: 'PhotoAnnotationEditor' }).vm.$emit('close')
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await wrapper.findAll('button').find(button => button.text() === 'Remove').trigger('click')
    await wrapper.setProps({ modelValue: [] })
    expect(revoke).toHaveBeenCalledWith('blob:site.jpg')
  })

  it('maps touch coordinates to the same image position after resizing and clamps outside drags', () => {
    expect(photoPoint(150, 100, { left: 50, top: 50, width: 200, height: 100 })).toEqual({ x: 0.5, y: 0.5 })
    expect(photoPoint(250, 150, { left: 50, top: 50, width: 400, height: 200 })).toEqual({ x: 0.5, y: 0.5 })
    expect(photoPoint(-50, 500, { left: 0, top: 0, width: 100, height: 100 })).toEqual({ x: 0, y: 1 })
  })
})
