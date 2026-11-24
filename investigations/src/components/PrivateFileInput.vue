<template>
  <div class="private-file-input">
    <input
      ref="input"
      type="file"
      hidden
      :disabled="disabled"
      :aria-label="label"
      @change="$emit('change', $event)"
    />
    <Button :disabled="disabled" icon-left="lucide-paperclip" @click="input?.click()">{{
      label
    }}</Button>
    <template v-if="annotationEnabled">
      <input ref="photoInput" type="file" hidden accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="disabled || Boolean(photo)" aria-label="Choose photo to annotate" @change="choosePhoto" />
      <Button type="button" :disabled="disabled || Boolean(photo)" @click="photoInput?.click()">Annotate photo</Button>
      <PhotoAnnotationEditor v-if="photo" :file="photo" @close="photo = null" @save="saveAnnotation" />
    </template>
  </div>
</template>
<script setup>
import { defineAsyncComponent, shallowRef, ref } from 'vue'
import { Button } from 'frappe-ui'
const PhotoAnnotationEditor = defineAsyncComponent(() => import('../../../frontend/src/components/PhotoAnnotationEditor.vue'))
defineProps({ label: { type: String, default: 'Attach file' }, disabled: Boolean, annotationEnabled: Boolean })
const emit = defineEmits(['change', 'annotated'])
const input = ref(null)
const photoInput = ref(null)
const photo = shallowRef(null)
function choosePhoto(event) {
  photo.value = event.target.files?.[0] || null
  event.target.value = ''
}
function saveAnnotation(annotated) {
  emit('annotated', { original: photo.value, annotated })
  photo.value = null
}
</script>
