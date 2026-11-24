<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { Button } from 'frappe-ui'
const PhotoAnnotationEditor = defineAsyncComponent(() => import('./PhotoAnnotationEditor.vue'))
const props = defineProps<{ modelValue: File[]; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [files: File[]]; busy: [busy: boolean] }>()
const editing = shallowRef<File | null>(null)
const previews = ref(new Map<File, string>())

function isPhoto(file: File) { return /^image\/(jpeg|png|webp|avif|heic|heif)$/i.test(file.type) || /\.(jpe?g|png|webp|avif|heic|heif)$/i.test(file.name) }
function select(event: Event) {
  if (props.disabled) return
  const input = event.target as HTMLInputElement
  emit('update:modelValue', [...props.modelValue, ...Array.from(input.files || [])])
  input.value = ''
}
function remove(index: number) {
  if (!props.disabled) emit('update:modelValue', props.modelValue.filter((_, at) => at !== index))
}
function annotate(file: File) { if (!props.disabled) { editing.value = file; emit('busy', true) } }
function close() { editing.value = null; emit('busy', false) }
function save(file: File) {
  if (!props.disabled) emit('update:modelValue', [...props.modelValue, file])
  close()
}
watch(() => props.modelValue, files => {
  const next = new Map<File, string>()
  for (const file of files) {
    if (isPhoto(file) && typeof URL.createObjectURL === 'function') next.set(file, previews.value.get(file) || URL.createObjectURL(file))
  }
  for (const [file, url] of previews.value) { if (!next.has(file)) URL.revokeObjectURL(url) }
  previews.value = next
}, { immediate: true })
onBeforeUnmount(() => { for (const url of previews.value.values()) URL.revokeObjectURL(url); emit('busy', false) })
</script>

<template>
  <div class="space-y-3">
    <input type="file" aria-label="Add attachments or photos" multiple :disabled="disabled || Boolean(editing)" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx" class="block w-full rounded border border-outline-gray-2 bg-surface-base px-3 py-2 text-sm text-ink-gray-7" @change="select" />
    <p v-if="modelValue.some(isPhoto)" class="text-xs text-ink-gray-5">Annotate adds a marked-up copy alongside the original photo.</p>
    <ul class="space-y-2">
      <li v-for="(file, index) in modelValue" :key="index" class="flex items-center gap-3 rounded border border-outline-gray-1 p-2">
        <img v-if="previews.get(file)" :src="previews.get(file)" alt="Selected photo" class="h-16 w-16 shrink-0 rounded object-cover" />
        <div class="min-w-0 flex-1">
          <p class="break-words text-sm text-ink-gray-8">{{ file.name }}</p>
          <div class="mt-1 flex flex-wrap gap-2">
            <Button v-if="isPhoto(file)" type="button" variant="subtle" size="sm" :disabled="disabled || Boolean(editing)" @click="annotate(file)">Annotate</Button>
            <Button type="button" variant="ghost" size="sm" :disabled="disabled || Boolean(editing)" :aria-label="`Remove ${file.name}`" @click="remove(index)">Remove</Button>
          </div>
        </div>
      </li>
    </ul>
    <PhotoAnnotationEditor v-if="editing" :file="editing" @close="close" @save="save" />
  </div>
</template>
