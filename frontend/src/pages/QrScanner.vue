<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import jsQR from 'jsqr'
import { apiRequest } from '../lib/api'
import { openAppBrowser } from '../lib/appBrowser'
import { parseQrLink, type QrDestination } from '../lib/qrLinks'

const router = useRouter()
const video = ref<HTMLVideoElement | null>(null)
const phase = ref<'starting' | 'scanning' | 'opening' | 'paused' | 'error'>('starting')
const error = ref('')
let stream: MediaStream | null = null
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0, alive = true
const canvas = document.createElement('canvas')

function stopCamera() {
  generation += 1
  clearTimeout(timer)
  timer = undefined
  stream?.getTracks().forEach(track => {
    track.removeEventListener?.('ended', pauseCamera)
    track.stop()
  })
  stream = null
  if (video.value) { video.value.pause(); video.value.srcObject = null }
}

async function openCode(value: string) {
  stopCamera()
  const token = generation
  phase.value = 'opening'; error.value = ''
  try {
    let target: QrDestination = parseQrLink(value)
    if (target.kind === 'desk') {
      const query = new URLSearchParams({ doctype: target.doctype, name: target.name })
      if (target.revision) query.set('revision', target.revision)
      const response = await apiRequest<any>(`/api/method/verto.api.mobile.qr_scanner.resolve_document?${query}`, { cache: 'no-store' })
      if (!alive || token !== generation) return
      target = parseQrLink(response.message.url)
      if (target.kind === 'desk') {
        openAppBrowser({ url: response.message.url, title: 'Scanned document' })
        phase.value = 'paused'
        return
      }
    }
    if (!alive || token !== generation) return
    if (target.kind === 'mobile') await router.replace(target.url)
    else if (target.kind === 'file') {
      openAppBrowser({ url: target.url, title: 'Scanned document' })
      phase.value = 'paused'
    }
  } catch (err) {
    if (!alive || token !== generation) return
    error.value = err instanceof Error ? err.message : 'Could not open this document.'
    phase.value = 'error'
  }
}

function scanFrame(token: number) {
  if (!alive || token !== generation || phase.value !== 'scanning') return
  const player = video.value
  try {
    if (player && player.readyState >= 2 && player.videoWidth && player.videoHeight) {
      const ratio = Math.min(1, 960 / Math.max(player.videoWidth, player.videoHeight))
      canvas.width = Math.round(player.videoWidth * ratio)
      canvas.height = Math.round(player.videoHeight * ratio)
      const context = canvas.getContext('2d', { willReadFrequently: true })
      if (!context) throw new Error('Camera scanning is not available in this browser.')
      context.drawImage(player, 0, 0, canvas.width, canvas.height)
      const frame = context.getImageData(0, 0, canvas.width, canvas.height)
      const code = jsQR(frame.data, frame.width, frame.height, { inversionAttempts: 'attemptBoth' })
      if (code?.data) { void openCode(code.data); return }
    }
    timer = setTimeout(() => scanFrame(token), 180)
  } catch (err) {
    stopCamera(); phase.value = 'error'
    error.value = err instanceof Error ? err.message : 'Could not read the camera. Try again.'
  }
}

async function startCamera() {
  stopCamera()
  const token = generation
  error.value = ''; phase.value = 'starting'
  try {
    if (window.isSecureContext === false || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Camera scanning needs a secure HTTPS connection and camera support.')
    }
    const camera = await navigator.mediaDevices.getUserMedia({ audio: false,
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } } })
    if (!alive || token !== generation) { camera.getTracks().forEach(track => track.stop()); return }
    stream = camera
    camera.getTracks().forEach(track => track.addEventListener?.('ended', pauseCamera, { once: true }))
    await nextTick()
    if (!alive || token !== generation || !video.value) return
    video.value.srcObject = camera
    await video.value.play()
    if (!alive || token !== generation) return
    phase.value = 'scanning'
    scanFrame(token)
  } catch (err) {
    if (!alive || token !== generation) return
    stopCamera(); phase.value = 'error'
    const name = err instanceof Error ? err.name : ''
    error.value = name === 'NotAllowedError' ? 'Camera access was denied. Allow camera access for this site in your browser settings, then try again.'
      : name === 'NotFoundError' ? 'No camera was found on this device.'
      : name === 'NotReadableError' ? 'The camera is busy. Close other camera apps, then try again.'
      : err instanceof Error ? err.message : 'Could not start the camera. Try again.'
  }
}

function pauseCamera() {
  if (!['starting', 'scanning', 'opening'].includes(phase.value)) return
  stopCamera(); phase.value = 'paused'
}
function visibilityChanged() { if (document.visibilityState === 'hidden') pauseCamera() }
function close() { stopCamera(); void router.replace('/') }
onMounted(() => {
  document.addEventListener('visibilitychange', visibilityChanged)
  window.addEventListener('pagehide', pauseCamera)
  void startCamera()
})
onBeforeUnmount(() => {
  alive = false; stopCamera()
  document.removeEventListener('visibilitychange', visibilityChanged)
  window.removeEventListener('pagehide', pauseCamera)
})
</script>

<template>
  <section class="mx-auto max-w-xl space-y-4 p-4 pb-24">
    <div class="flex items-center justify-between gap-3">
      <h1 class="text-xl-semibold text-ink-gray-9">Scan QR code</h1>
      <Button variant="subtle" @click="close">Close</Button>
    </div>
    <p class="text-sm text-ink-gray-6">Point the rear camera at a document or form QR code from this site.</p>
    <div class="relative aspect-[4/3] overflow-hidden rounded-7 bg-black">
      <video ref="video" autoplay playsinline :muted="true" class="h-full w-full object-contain" aria-label="QR scanner camera preview" />
      <div v-if="phase === 'scanning'" class="pointer-events-none absolute inset-[12%] rounded-7 border-2 border-white/80" aria-hidden="true" />
    </div>
    <p role="status" aria-live="polite" class="text-sm text-ink-gray-7">
      {{ phase === 'starting' ? 'Starting camera…' : phase === 'opening' ? 'Opening document…' : phase === 'scanning' ? 'Keep the QR code steady and fully in view.' : phase === 'paused' ? 'Camera paused. Tap Scan again to scan another code.' : '' }}
    </p>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <Button v-if="phase === 'paused' || phase === 'error'" variant="solid" @click="startCamera">Scan again</Button>
  </section>
</template>
