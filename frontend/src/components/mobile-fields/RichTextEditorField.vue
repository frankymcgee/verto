<template>
  <div class="space-y-1.5">
    <label v-if="label" class="block text-sm-medium text-ink-gray-8">
      {{ label }}
      <span v-if="required" class="text-red-500" aria-hidden="true">*</span>
    </label>

    <p v-if="description" class="text-xs leading-4 text-ink-gray-5">
      {{ description }}
    </p>

    <Editor
      :model-value="editorContent"
      :extensions="extensions"
      format="html"
      :placeholder="placeholder || label || ''"
      :editable="!disabled"
      @update:model-value="handleChange"
    >
      <div class="overflow-hidden rounded-5 border border-outline-gray-2">
        <EditorFixedMenu
          v-if="!disabled"
          :items="toolbarButtons"
          class="flex-wrap border-b border-outline-gray-2 bg-surface-gray-1 p-2"
        />
        <EditorContent
          :class="editorClass"
          :aria-label="label || 'Rich text editor'"
          :aria-required="required ? 'true' : undefined"
          :aria-disabled="disabled ? 'true' : undefined"
        />
      </div>
    </Editor>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Editor,
  EditorContent,
  EditorFixedMenu,
  RichTextKit,
  H2,
  H3,
  Paragraph,
  Separator,
  Bold,
  Italic,
  BulletList,
  OrderedList,
  Blockquote,
  InsertLink,
  Undo,
  Redo,
} from 'frappe-ui/editor'

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

const extensions = [
  RichTextKit.configure({ mention: false, slashCommands: false }),
]
const toolbarButtons = [
  H2,
  H3,
  Paragraph,
  Separator,
  Bold,
  Italic,
  BulletList,
  OrderedList,
  Blockquote,
  InsertLink,
  Separator,
  Undo,
  Redo,
]

const editorContent = computed(() => String(props.modelValue || ''))

const editorClass =
  'min-h-32 max-w-none bg-surface-base px-3 py-2 text-base text-ink-gray-8 outline-none'

function normaliseHtml(value: string) {
  const html = String(value || '').trim()
  const compact = html.replace(/\s+/g, '').toLowerCase()

  if (!html || compact === '<p></p>' || compact === '<p><br></p>') {
    return ''
  }

  return html
}

function handleChange(value: unknown) {
  const html = normaliseHtml(typeof value === 'string' ? value : '')

  emit('update:modelValue', html)
  emit('change', html)
}
</script>
