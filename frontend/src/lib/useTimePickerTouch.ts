import { watch, type Ref } from 'vue'

const optionSelector = '.time-picker-panel button[role="option"]'
const tapTolerance = 10

export function useTimePickerTouch(open: Ref<boolean>) {
  let activeTouch: { option: HTMLButtonElement; id: number; x: number; y: number } | null = null

  function resetTouch() {
    activeTouch = null
  }

  function startTouch(event: TouchEvent) {
    resetTouch()
    if (event.touches.length !== 1 || !(event.target instanceof Element)) return

    const option = event.target.closest<HTMLButtonElement>(optionSelector)
    if (!option) return

    const { identifier, clientX, clientY } = event.touches[0]
    activeTouch = { option, id: identifier, x: clientX, y: clientY }
  }

  function trackTouch(event: TouchEvent) {
    if (!activeTouch) return

    const touch = event.changedTouches[0]
    if (!touch || touch.identifier !== activeTouch.id ||
        Math.hypot(touch.clientX - activeTouch.x, touch.clientY - activeTouch.y) > tapTolerance) {
      resetTouch()
    }
  }

  function finishTouch(event: TouchEvent) {
    trackTouch(event)
    const tap = activeTouch
    resetTouch()
    if (!tap?.option.isConnected || event.touches.length) return

    // Use Frappe's own selection action before the browser's compatibility click.
    event.preventDefault()
    tap.option.click()
  }

  watch(open, (isOpen, _, onCleanup) => {
    if (!isOpen) return

    // Frappe teleports the list to the page. Listen only while the picker is open.
    const listeners = new AbortController()
    const capture = { capture: true, signal: listeners.signal }
    const passive = { ...capture, passive: true }
    document.addEventListener('touchstart', startTouch, passive)
    document.addEventListener('touchmove', trackTouch, passive)
    document.addEventListener('touchcancel', resetTouch, passive)
    document.addEventListener('touchend', finishTouch, { ...capture, passive: false })
    onCleanup(() => {
      listeners.abort()
      resetTouch()
    })
  }, { flush: 'sync' })

  function handleTimePickerBlur(event: FocusEvent) {
    // Let a tap finish when the trigger blurs before Frappe's option activates.
    if (open.value && (activeTouch || !event.relatedTarget)) event.stopPropagation()
  }

  return { handleTimePickerBlur }
}
