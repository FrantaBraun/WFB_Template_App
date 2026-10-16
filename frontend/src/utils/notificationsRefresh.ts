/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef } from 'react'

/** Window event meaning "notifications may have changed - refetch them now". */
export const NOTIFICATIONS_REFRESH_EVENT = 'notifications:refresh'

/**
 * The header bell polls every minute, so a notification the user's own action
 * just created (a manual check that found a new version) would otherwise not
 * show until the next poll or a page reload. Whoever causes one calls this and
 * everything showing notifications refetches immediately.
 */
export function requestNotificationsRefresh(): void {
  window.dispatchEvent(new Event(NOTIFICATIONS_REFRESH_EVENT))
}

/** Runs `handler` whenever a refresh is requested; always calls the latest handler. */
export function useOnNotificationsRefresh(handler: () => void): void {
  const handlerRef = useRef(handler)
  useEffect(() => {
    handlerRef.current = handler
  })

  useEffect(() => {
    const listener = () => handlerRef.current()
    window.addEventListener(NOTIFICATIONS_REFRESH_EVENT, listener)
    return () => window.removeEventListener(NOTIFICATIONS_REFRESH_EVENT, listener)
  }, [])
}
