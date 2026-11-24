import { ref } from 'vue'

export function isFormPath(path: string) {
  return /\/(?:new|edit|voice-jha|jha)\//.test(path)
}

// Seed from the address before the router resolves a directly opened form.
export const formOpen = ref(typeof window !== 'undefined' && isFormPath(window.location.pathname))

export function setFormPath(path: string) {
  formOpen.value = isFormPath(path)
}
