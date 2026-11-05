<template>
  <Teleport to="body">
    <div
      v-if="hoverCard"
      ref="hoverCardElement"
      class="year-hover-card"
      :class="`year-hover-card-${hoverCard.type}`"
      :style="hoverCardStyle"
      role="tooltip"
    >
      <div class="year-hover-card-header">
        <div class="min-w-0">
          <div class="year-hover-card-kicker">{{ hoverCard.kicker }}</div>
          <div class="year-hover-card-title truncate">{{ hoverCard.title }}</div>
          <div v-if="hoverCard.subtitle" class="year-hover-card-subtitle truncate">
            {{ hoverCard.subtitle }}
          </div>
        </div>

        <div
          v-if="hoverCard.badge || hoverCard.secondaryBadge"
          class="year-hover-card-badge-stack"
        >
          <span
            v-if="hoverCard.badge"
            class="year-hover-card-badge"
            :class="`year-hover-card-badge-${hoverCard.badgeTone || 'gray'}`"
          >
            {{ hoverCard.badge }}
          </span>
          <span
            v-if="hoverCard.secondaryBadge"
            class="year-hover-card-badge"
            :class="`year-hover-card-badge-${hoverCard.secondaryBadgeTone || 'gray'}`"
          >
            {{ hoverCard.secondaryBadge }}
          </span>
        </div>
      </div>

      <div class="year-hover-card-grid">
        <template v-for="row in hoverCard.rows" :key="row.label">
          <div v-if="row.value !== undefined && row.value !== null && row.value !== ''" class="year-hover-card-label">
            {{ row.label }}
          </div>
          <div v-if="row.value !== undefined && row.value !== null && row.value !== ''" class="year-hover-card-value truncate">
            {{ row.value }}
          </div>
        </template>
      </div>

      <div v-if="hoverCard.note" class="year-hover-card-note">
        {{ hoverCard.note }}
      </div>
    </div>
  </Teleport>
</template>

<script lang="ts">
export type HoverCardRow = {
  label: string
  value?: string | number | null
}

export type HoverCard = {
  type: 'shift' | 'project' | 'leave' | 'day-marker' | 'employee'
  kicker: string
  title: string
  subtitle?: string
  badge?: string
  badgeTone?: 'green' | 'red' | 'gray' | 'blue' | 'yellow'
  secondaryBadge?: string
  secondaryBadgeTone?: 'green' | 'red' | 'gray' | 'blue' | 'yellow'
  accent?: string
  rows: HoverCardRow[]
  note?: string
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'

const hoverCard = shallowRef<HoverCard | null>(null)
const hoverCardElement = ref<HTMLDivElement | null>(null)

type HoverPointer = {
  clientX: number
  clientY: number
}

let hoverPositionFrame = 0
let pendingHoverPointer: HoverPointer | null = null
let hoverHideTimer: number | null = null
let activeHoverKey = ''

const hoverCardStyle = computed(() => ({
  '--year-hover-accent': hoverCard.value?.accent || 'rgb(59 130 246)',
}))

function getHoverPointer(event: MouseEvent): HoverPointer {
  return {
    clientX: event.clientX,
    clientY: event.clientY,
  }
}

function applyHoverCardPosition(pointer: HoverPointer) {
  if (!hoverCard.value || !hoverCardElement.value) return

  const padding = 12
  const cursorOffset = 14
  const fallbackCardWidth = 340
  const fallbackCardHeight = hoverCard.value.type === 'project' ? 168 : hoverCard.value.type === 'leave' ? 210 : hoverCard.value.type === 'employee' ? 280 : 240
  const cardWidth = hoverCardElement.value.offsetWidth || fallbackCardWidth
  const cardHeight = hoverCardElement.value.offsetHeight || fallbackCardHeight
  const maxLeft = Math.max(padding, window.innerWidth - cardWidth - padding)
  const maxTop = Math.max(padding, window.innerHeight - cardHeight - padding)

  let x = pointer.clientX + cursorOffset
  if (x + cardWidth + padding > window.innerWidth) {
    x = pointer.clientX - cardWidth - cursorOffset
  }

  let y = pointer.clientY + cursorOffset
  if (y + cardHeight + padding > window.innerHeight) {
    y = pointer.clientY - cardHeight - cursorOffset
  }

  const clampedX = Math.min(Math.max(padding, x), maxLeft)
  const clampedY = Math.min(Math.max(padding, y), maxTop)

  hoverCardElement.value.style.transform = `translate3d(${clampedX}px, ${clampedY}px, 0)`
}

function scheduleHoverCardPosition(event: MouseEvent) {
  if (!hoverCard.value) return

  pendingHoverPointer = getHoverPointer(event)
  if (hoverPositionFrame) return

  hoverPositionFrame = window.requestAnimationFrame(() => {
    hoverPositionFrame = 0
    if (pendingHoverPointer) applyHoverCardPosition(pendingHoverPointer)
    pendingHoverPointer = null
  })
}

function cancelScheduledHoverClear() {
  if (hoverHideTimer !== null) {
    window.clearTimeout(hoverHideTimer)
    hoverHideTimer = null
  }
}

function setHoverCard(key: string, card: HoverCard, event: MouseEvent) {
  cancelScheduledHoverClear()

  if (activeHoverKey !== key || !hoverCard.value) {
    activeHoverKey = key
    hoverCard.value = card
  }

  // Vue renders the new content before the next frame. Measure it only once,
  // using the newest pointer position, and cancel this work on hide/unmount.
  scheduleHoverCardPosition(event)
}

function moveHoverCard(event: MouseEvent) {
  scheduleHoverCardPosition(event)
}

function scheduleClearHoverCard(delay = 90) {
  cancelScheduledHoverClear()
  hoverHideTimer = window.setTimeout(() => {
    clearHoverCard()
  }, delay)
}

function clearHoverCard() {
  cancelScheduledHoverClear()

  if (hoverPositionFrame) {
    window.cancelAnimationFrame(hoverPositionFrame)
    hoverPositionFrame = 0
  }

  activeHoverKey = ''
  pendingHoverPointer = null
  hoverCard.value = null
}

onBeforeUnmount(clearHoverCard)

defineExpose({ setHoverCard, moveHoverCard, scheduleClearHoverCard, clearHoverCard })
</script>

<style scoped>
.year-hover-card {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 45;
  width: 340px;
  transform: translate3d(-9999px, -9999px, 0);
  will-change: transform;
  max-width: calc(100vw - 24px);
  pointer-events: none;
  border: 1px solid rgb(209 213 219);
  border-left: 4px solid var(--year-hover-accent, rgb(59 130 246));
  border-radius: 10px;
  background: rgb(255 255 255);
  box-shadow: 0 18px 40px rgb(15 23 42 / 0.18), 0 4px 12px rgb(15 23 42 / 0.1);
  color: rgb(31 41 55);
  max-height: calc(100vh - 24px);
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  contain: layout paint style;
  backface-visibility: hidden;
}

.year-hover-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(229 231 235);
  background: linear-gradient(90deg, rgb(249 250 251), rgb(255 255 255));
  padding: 10px 12px 8px;
}

.year-hover-card-kicker {
  color: rgb(107 114 128);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  line-height: 1;
  text-transform: uppercase;
}

.year-hover-card-title {
  margin-top: 4px;
  color: rgb(17 24 39);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.year-hover-card-subtitle {
  margin-top: 3px;
  color: rgb(75 85 99);
  font-size: 11px;
  font-weight: 500;
  line-height: 1.2;
}

.year-hover-card-badge-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  margin-left: 12px;
}

.year-hover-card-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: max-content;
  border-radius: 9999px;
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.year-hover-card-badge-green {
  background: rgb(220 252 231);
  color: rgb(22 101 52);
}

.year-hover-card-badge-red {
  background: rgb(254 226 226);
  color: rgb(153 27 27);
}

.year-hover-card-badge-blue {
  background: rgb(219 234 254);
  color: rgb(30 64 175);
}

.year-hover-card-badge-yellow {
  background: rgb(254 249 195);
  color: rgb(113 63 18);
}

.year-hover-card-badge-gray {
  background: rgb(243 244 246);
  color: rgb(55 65 81);
}

.year-hover-card-grid {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 5px 10px;
  padding: 10px 12px;
}

.year-hover-card-label {
  color: rgb(107 114 128);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  text-transform: uppercase;
}

.year-hover-card-value {
  color: rgb(31 41 55);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
}

.year-hover-card-project .year-hover-card-value {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

.year-hover-card-note {
  margin: 0 12px 12px;
  border: 1px solid rgb(254 202 202);
  border-radius: 8px;
  background: rgb(254 242 242);
  padding: 8px;
  color: rgb(127 29 29);
  font-size: 11px;
  font-weight: 500;
  line-height: 1.35;
  white-space: pre-line;
}

.year-hover-card-leave .year-hover-card-note {
  border-color: rgb(251 207 232);
  background: rgb(253 242 248);
  color: rgb(157 23 77);
}

.year-hover-card-day-marker .year-hover-card-note {
  border-color: rgb(191 219 254);
  background: rgb(239 246 255);
  color: rgb(30 64 175);
}
</style>
