export async function clearNotificationIndicators() {
  if (document.visibilityState !== 'visible') return

  await Promise.allSettled([
    navigator.clearAppBadge?.(),
    (async () => {
      const registration = await navigator.serviceWorker?.getRegistration(window.location.href)
      if (new URL(registration?.scope || '/', window.location.origin).pathname.replace(/\/$/, '') !== '/verto-mobile') return
      const notifications = await registration?.getNotifications?.()
      notifications?.forEach((notification) => notification.close())
    })(),
  ])
}
