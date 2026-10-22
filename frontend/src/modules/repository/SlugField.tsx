/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, slugify, type SlugCheck } from './api'
import { hintClass, inputClass, labelClass } from './ui'

const CHECK_DEBOUNCE_MS = 300

export type SlugStatus = 'idle' | 'checking' | 'ok' | 'bad'

interface Props {
  scope: 'repository' | 'table' | 'record'
  /** The repository's slug, for the table and record scopes. */
  repository?: string
  /** The table's slug, for the record scope. */
  table?: string
  /** What the slug is made from while the user has not typed one of their own. */
  name: string
  value: string
  onChange: (slug: string) => void
  /** The slug the edited row has now: it counts as free. Leave out when creating. */
  currentSlug?: string
  /** True when creating: the slug follows the name until the user edits it. */
  autoFromName: boolean
  /** Told whenever the live check's answer changes, so the form can hold back its Save button. */
  onStatus?: (status: SlugStatus) => void
  /** A server-side error code for the slug ("taken", "invalid", "reserved") from the last save attempt. */
  serverError?: string | null
}

/**
 * A slug input that makes the slug from the name (until the user edits it),
 * and checks it live against the server: invalid, reserved, or taken - with
 * the nearest free one offered. While the slug follows the name, a taken one
 * is replaced by the suggestion on its own. The unique constraint on the
 * server stays the final word (a save can still answer 409).
 */
export default function SlugField({ scope, repository, table, name, value, onChange, currentSlug, autoFromName, onStatus, serverError }: Props) {
  const { t } = useTranslation('repository')
  const inputId = useId()
  const [manual, setManual] = useState(!autoFromName)
  const [check, setCheck] = useState<SlugCheck | null>(null)
  const [failed, setFailed] = useState(false)
  const latest = useRef(0)

  // While automatic, the slug is whatever the name makes.
  useEffect(() => {
    if (!manual) onChange(slugify(name))
    // onChange is the parent's setter; the name is what drives this
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, manual])

  const status: SlugStatus = value === '' ? 'idle' : failed ? 'idle' : value === currentSlug ? 'ok' : check?.slug === value ? (check.available ? 'ok' : 'bad') : 'checking'

  useEffect(() => {
    onStatus?.(status)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  useEffect(() => {
    if (value === '' || value === currentSlug) return
    const ticket = ++latest.current
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ scope, slug: value })
      if (repository) params.set('repository', repository)
      if (table) params.set('table', table)
      if (currentSlug) params.set('exclude', currentSlug)
      fetchJson<SlugCheck>(`${API_BASE}/slug-check?${params}`)
        .then((answer) => {
          if (ticket !== latest.current) return
          setFailed(false)
          // Following the name: a taken slug becomes the suggested free one.
          if (!manual && !answer.available && answer.reason === 'taken' && answer.suggestion) onChange(answer.suggestion)
          else setCheck(answer)
        })
        .catch(() => ticket === latest.current && setFailed(true))
    }, CHECK_DEBOUNCE_MS)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, scope, repository, table, currentSlug, manual])

  const reason = check?.slug === value && !check.available ? check.reason : serverError && value !== '' ? serverError : null

  return (
    <div>
      <label htmlFor={inputId} className={labelClass}>
        {t('slug.label')}
      </label>
      <input
        id={inputId}
        value={value}
        onChange={(e) => {
          setManual(true)
          onChange(e.target.value.toLowerCase())
        }}
        maxLength={80}
        autoComplete="off"
        spellCheck={false}
        aria-describedby={`${inputId}-status`}
        aria-invalid={reason !== null}
        className={`${inputClass} font-mono text-sm`}
      />
      <p id={`${inputId}-status`} className={`${hintClass} min-h-[1.25rem]`} aria-live="polite">
        {value === '' && t('slug.empty')}
        {status === 'checking' && t('slug.checking')}
        {status === 'ok' && value !== '' && <span className="text-emerald-700 dark:text-emerald-400">{t('slug.available')}</span>}
        {reason && <span className="text-red-600 dark:text-red-400">{t(`slug.${reason}`)}</span>}
        {check?.slug === value && check.reason === 'taken' && check.suggestion && (
          <>
            {' '}
            <button
              type="button"
              onClick={() => {
                setManual(true)
                onChange(check.suggestion as string)
              }}
              className="repo-focus repo-accent-text underline"
            >
              {t('slug.useSuggestion', { slug: check.suggestion })}
            </button>
          </>
        )}
        {manual && autoFromName && (
          <>
            {' '}
            <button type="button" onClick={() => setManual(false)} className="repo-focus text-slate-600 underline dark:text-slate-300">
              {t('slug.fromName')}
            </button>
          </>
        )}
      </p>
    </div>
  )
}
