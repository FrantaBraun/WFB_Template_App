/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api/client'
import useDebouncedValue from './useDebouncedValue'

const SEARCH_DEBOUNCE_MS = 300

interface Loaded<T> {
  query: string
  items: T[]
}

export interface SearchableList<T> {
  /** null until the first successful load, and again after a failed one. */
  items: T[] | null
  /** The search `items` answers - lags behind the typed one while a new search is in flight. */
  answeredQuery: string
  failed: boolean
  /** The typed search is not what `items` shows yet (still debouncing, or the request is in flight). */
  pending: boolean
  /** Edits the loaded list in place, e.g. to show something the user just created before the next search. */
  update: (change: (items: T[]) => T[]) => void
}

/**
 * Loads a list endpoint with the server-side free-text search (`?q=`), for the
 * API documentation, collection and integration lists. `rawQuery` is the text
 * as typed: it is trimmed, and the request waits until typing pauses. The
 * previous result stays up (flagged `pending`) while the next one loads rather
 * than flashing empty. `path === null` means nothing to load (signed out).
 */
export default function useSearchableList<T>(path: string | null, rawQuery: string): SearchableList<T> {
  const query = rawQuery.trim()
  const searched = useDebouncedValue(query, SEARCH_DEBOUNCE_MS)
  const [loaded, setLoaded] = useState<Loaded<T> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (path === null) return
    // Responses can arrive out of order; one for a search the user has since
    // moved on from must not replace the newer search's result.
    let cancelled = false
    apiFetch(searched ? `${path}?q=${encodeURIComponent(searched)}` : path)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((items: T[]) => {
        if (cancelled) return
        setLoaded({ query: searched, items })
        setFailed(false)
      })
      .catch(() => {
        if (cancelled) return
        setLoaded(null)
        setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [path, searched])

  const update = useCallback((change: (items: T[]) => T[]) => {
    setLoaded((prev) => ({ query: prev?.query ?? '', items: change(prev?.items ?? []) }))
  }, [])

  return {
    items: loaded?.items ?? null,
    answeredQuery: loaded?.query ?? '',
    failed,
    pending: path !== null && !failed && loaded?.query !== query,
    update,
  }
}
