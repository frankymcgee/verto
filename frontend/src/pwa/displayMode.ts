export function isStandalonePwa() {
  const navigatorWithStandalone = navigator as Navigator & {
    standalone?: boolean
  }

  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    navigatorWithStandalone.standalone === true
  )
}

export function isAndroidDevice() {
  return /Android/i.test(navigator.userAgent)
}

export function isIosDevice() {
  return /iPad|iPhone|iPod/i.test(navigator.userAgent)
}

export function isAndroidStandalonePwa() {
  return isAndroidDevice() && isStandalonePwa()
}
