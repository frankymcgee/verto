<template>
  <div class="space-y-1.5">
    <label
      v-if="label"
      class="block text-sm font-medium text-ink-gray-8"
    >
      {{ label }}
      <span
        v-if="required"
        class="text-red-500"
        aria-hidden="true"
      >*</span>
    </label>

    <p
      v-if="description"
      class="text-xs leading-4 text-ink-gray-5"
    >
      {{ description }}
    </p>

    <TextEditor
      :content="editorContent"
      :placeholder="placeholder || label || ''"
      :editable="!disabled"
      :fixed-menu="disabled ? false : toolbarButtons"
      :editor-class="editorClass"
      :aria-label="label || 'Rich text editor'"
      :aria-required="required ? 'true' : undefined"
      :aria-disabled="disabled ? 'true' : undefined"
      @change="handleChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TextEditor } from 'frappe-ui'

const props = withDefaults(
  defineProps<{
    modelValue?: string | null
    label?: string
    description?: string
    placeholder?: string
    required?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    label: '',
    description: '',
    placeholder: '',
    required: false,
    disabled: false,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
}>()

const toolbarButtons = [
  ['Heading 2', 'Heading 3'],
  'Paragraph',
  'Separator',
  'Bold',
  'Italic',
  'Bullet List',
  'Numbered List',
  'Blockquote',
  'Link',
  'Separator',
  'Undo',
  'Redo',
]

const editorContent = computed(() => String(props.modelValue || ''))

const editorClass = computed(() => [
  'min-h-32 max-w-none bg-surface-white px-3 py-2 text-sm text-ink-gray-8',
  props.disabled
    ? 'rounded-lg border border-outline-gray-2 bg-surface-gray-1'
    : 'rounded-b-lg border border-t-0 border-outline-gray-2',
])

function normaliseHtml(value: string) {
  const html = String(value || '').trim()
  const compact = html.replace(/\s+/g, '').toLowerCase()

  if (!html || compact === '<p></p>' || compact === '<p><br></p>') {
    return ''
  }

  return html
}

function handleChange(value: string) {
  const html = normaliseHtml(value)

  emit('update:modelValue', html)
  emit('change', html)
}
</script>
