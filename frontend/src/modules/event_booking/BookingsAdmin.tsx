/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  FormRenderer,
  FormStats,
  SubmissionView,
  collectAnswers,
  type FormDefinition,
  type FormStatsData,
  type FormValues,
  type Question,
  type SubmissionEntry,
} from '../forms'
import SlotPicker, { type SlotChoice } from './SlotPicker'
import {
  API_BASE,
  errorsOf,
  fetchJson,
  formatDateTime,
  formatSlot,
  sendJson,
  statusOf,
  stringErrors,
  type BookingChange,
  type BookingDetail,
  type BookingMutation,
  type BookingRow,
  type BookingRowPage,
  type BookingStatus,
  type FreeDay,
  type RegistrationAdmin,
  type SlotInfo,
} from './api'
import { cardClass, dangerButtonClass, errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass, secondaryButtonClass, smallInputClass } from './ui'

const FORMS_API = '/api/modules/forms'
const PAGE_SIZE = 25
/** The server limits the offer to its own horizon; this only keeps the calendar from stopping early. */
const ADMIN_HORIZON_DAYS = 1000

const FIELD_ERROR_KEYS: Record<string, string> = {
  'slot:not_offered': 'admin.errors.slotNotOffered',
  'slot:full': 'admin.errors.slotFull',
  '_form:no_change': 'admin.errors.noChange',
  '_form:cancelled': 'admin.errors.cancelled',
  'email:invalid': 'admin.errors.emailInvalid',
  'name:invalid': 'admin.errors.nameInvalid',
}

/** The answers of a snapshot as the values a form holds (so the edit form starts from what was answered). */
function valuesFromAnswers(entries: SubmissionEntry[]): FormValues {
  const values: FormValues = {}
  for (const entry of entries) {
    if (!entry.shown || entry.value === null || entry.value === undefined) continue
    values[entry.question_id] = Array.isArray(entry.value) ? entry.value.map(String) : String(entry.value)
  }
  return values
}

function statusBadge(status: BookingStatus, label: string) {
  const colour =
    status === 'confirmed'
      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
      : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${colour}`}>{label}</span>
}

// --- The table of bookings ------------------------------------------------------------------------------

/**
 * The bookings of one registration: a table (with a filter by state, a search
 * in name and e-mail, and ordering by slot), each opening its detail, and the
 * summary of the answers of the confirmed ones. Used on the event's editor
 * page (the "event.editor" slot) and on the registration's own page.
 */
export default function BookingsAdmin({ registrationId }: { registrationId: string }) {
  const { t, i18n } = useTranslation('event_booking')
  const [status, setStatus] = useState<'' | BookingStatus>('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [descending, setDescending] = useState(false)
  const [rows, setRows] = useState<BookingRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [failed, setFailed] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [stats, setStats] = useState<FormStatsData | null>(null)
  const [statsOpen, setStatsOpen] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search])

  const listPath = useCallback(
    (offset: number) => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset), sort: descending ? 'desc' : 'asc' })
      if (status) params.set('status', status)
      if (query) params.set('q', query)
      return `${API_BASE}/manage/registrations/${registrationId}/bookings?${params}`
    },
    [registrationId, status, query, descending],
  )

  useEffect(() => {
    let cancelled = false
    setFailed(false)
    fetchJson<BookingRowPage>(listPath(0))
      .then((page) => {
        if (cancelled) return
        setRows(page.items)
        setTotal(page.total)
      })
      .catch(() => !cancelled && (setFailed(true), setRows([])))
    return () => {
      cancelled = true
    }
  }, [listPath, reload])

  useEffect(() => {
    if (!statsOpen) return
    let cancelled = false
    fetchJson<FormStatsData>(`${API_BASE}/manage/registrations/${registrationId}/answers/stats`)
      .then((found) => !cancelled && setStats(found))
      .catch(() => !cancelled && setStats(null))
    return () => {
      cancelled = true
    }
  }, [registrationId, statsOpen, reload])

  async function loadMore() {
    if (!rows) return
    setLoadingMore(true)
    try {
      const page = await fetchJson<BookingRowPage>(listPath(rows.length))
      setRows([...rows, ...page.items])
      setTotal(page.total)
    } catch {
      setFailed(true)
    } finally {
      setLoadingMore(false)
    }
  }

  if (selected) {
    return (
      <BookingDetailView
        registrationId={registrationId}
        bookingId={selected}
        onBack={() => setSelected(null)}
        onChanged={() => setReload((value) => value + 1)}
      />
    )
  }

  const allDay = t('picker.allDay')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={`status-${registrationId}`} className={labelClass}>{t('admin.filterStatus')}</label>
          <select id={`status-${registrationId}`} value={status} onChange={(e) => setStatus(e.target.value as '' | BookingStatus)} className={smallInputClass}>
            <option value="">{t('admin.statusAll')}</option>
            <option value="confirmed">{t('admin.status.confirmed')}</option>
            <option value="cancelled">{t('admin.status.cancelled')}</option>
          </select>
        </div>
        <div className="min-w-0 flex-1 basis-48">
          <label htmlFor={`search-${registrationId}`} className={labelClass}>{t('admin.search')}</label>
          <input id={`search-${registrationId}`} type="search" value={search} onChange={(e) => setSearch(e.target.value)} className={`${smallInputClass} w-full`} />
        </div>
        <button type="button" onClick={() => setDescending((value) => !value)} className={secondaryButtonClass} aria-pressed={descending}>
          {descending ? t('admin.sortLatest') : t('admin.sortEarliest')}
        </button>
        <button type="button" onClick={() => setStatsOpen((open) => !open)} aria-expanded={statsOpen} className={secondaryButtonClass}>
          {t('admin.stats')}
        </button>
      </div>

      {statsOpen && (
        <div className={cardClass}>
          <h3 className="mb-1 font-semibold">{t('admin.statsTitle')}</h3>
          <p className={`mb-3 ${mutedClass}`}>{t('admin.statsHint')}</p>
          {stats ? <FormStats stats={stats} /> : <p className={mutedClass}>{t('common.loading')}</p>}
        </div>
      )}

      {failed && <p role="alert" className={errorClass}>{t('admin.loadError')}</p>}
      {rows === null && !failed && <p className={mutedClass}>{t('common.loading')}</p>}
      {rows && rows.length === 0 && !failed && <p className={mutedClass}>{query || status ? t('admin.noMatch') : t('admin.noBookings')}</p>}

      {rows && rows.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-950 dark:text-slate-400">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">{t('admin.columns.slot')}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t('admin.columns.name')}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t('admin.columns.email')}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t('admin.columns.status')}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t('admin.columns.created')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                    <td className="px-3 py-2">
                      <button type="button" onClick={() => setSelected(row.id)} className="text-left underline">
                        {formatSlot(row.slot_date, row.slot_time, i18n.language, allDay)}
                      </button>
                    </td>
                    <td className="px-3 py-2">
                      {row.name}
                      {row.has_history && <span title={t('admin.hasHistory')} aria-label={t('admin.hasHistory')} className="ml-1 text-xs">✎</span>}
                    </td>
                    <td className="max-w-[14rem] truncate px-3 py-2">{row.email}</td>
                    <td className="px-3 py-2">{statusBadge(row.status, t(`admin.status.${row.status}`))}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-slate-500 dark:text-slate-400">{formatDateTime(row.created_at, i18n.language)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={mutedClass}>{t('admin.shown', { count: rows.length, total })}</p>
            {rows.length < total && (
              <button type="button" onClick={loadMore} disabled={loadingMore} className={secondaryButtonClass}>
                {t('admin.loadMore')}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// --- One booking -------------------------------------------------------------------------------------

function changeLines(change: BookingChange, t: (key: string, options?: Record<string, unknown>) => string, allDay: string): string[] {
  const lines: string[] = []
  const { changes } = change
  if (changes.slot_date || changes.slot_time) {
    const from = (changes.slot_date?.from ?? '') + (changes.slot_time ? ` ${changes.slot_time.from ?? allDay}` : '')
    const to = (changes.slot_date?.to ?? '') + (changes.slot_time ? ` ${changes.slot_time.to ?? allDay}` : '')
    lines.push(t('admin.history.slot', { from: from.trim(), to: to.trim() }))
  }
  if (changes.name) lines.push(t('admin.history.name', { from: changes.name.from, to: changes.name.to }))
  if (changes.email) lines.push(t('admin.history.email', { from: changes.email.from, to: changes.email.to }))
  if (changes.answers) lines.push(t('admin.history.answers', { questions: changes.answers.questions.map((question) => question.label).join(', ') }))
  return lines
}

function History({ history }: { history: BookingChange[] }) {
  const { t, i18n } = useTranslation('event_booking')
  const allDay = t('picker.allDay')
  if (history.length === 0) return <p className={mutedClass}>{t('admin.history.empty')}</p>
  return (
    <ol className="space-y-3">
      {history.map((change) => (
        <li key={change.id} className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
          <p className="font-medium">
            {change.kind === 'cancelled' ? t('admin.history.cancelled') : t('admin.history.updated')}
            <span className="ml-2 font-normal text-slate-500 dark:text-slate-400">{formatDateTime(change.created_at, i18n.language)}</span>
          </p>
          <p className={mutedClass}>{t('admin.history.by', { who: change.user_sub ? change.user_sub.slice(0, 8) : '–' })}</p>
          {change.kind === 'updated' && (
            <ul className="mt-1 list-disc pl-5">
              {changeLines(change, t, allDay).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {change.note && (
            <p className="mt-1 whitespace-pre-line">
              <span className="text-slate-500 dark:text-slate-400">{t('admin.history.note')}: </span>
              {change.note}
            </p>
          )}
          <p className={`mt-1 text-xs ${change.email_error ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`}>
            {change.notified ? t('admin.history.emailSent') : change.email_error ? t('admin.history.emailFailed', { error: change.email_error }) : t('admin.history.emailNotSent')}
          </p>
        </li>
      ))}
    </ol>
  )
}

function BookingDetailView({
  registrationId,
  bookingId,
  onBack,
  onChanged,
}: {
  registrationId: string
  bookingId: string
  onBack: () => void
  onChanged: () => void
}) {
  const { t, i18n } = useTranslation('event_booking')
  const [detail, setDetail] = useState<BookingDetail | null>(null)
  const [registration, setRegistration] = useState<RegistrationAdmin | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [failed, setFailed] = useState(false)
  const [editing, setEditing] = useState(false)
  const [outcome, setOutcome] = useState<{ kind: 'updated' | 'cancelled'; emailSent: boolean | null } | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetchJson<BookingDetail>(`${API_BASE}/manage/bookings/${bookingId}`),
      fetchJson<RegistrationAdmin>(`${API_BASE}/manage/registrations/${registrationId}`),
    ])
      .then(async ([booking, reg]) => {
        const form = await fetchJson<FormDefinition>(`${FORMS_API}/manage/${reg.form_id}`)
        if (cancelled) return
        setDetail(booking)
        setRegistration(reg)
        setQuestions(form.questions)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [bookingId, registrationId])

  if (failed) {
    return (
      <div className="space-y-3">
        <button type="button" onClick={onBack} className={secondaryButtonClass}>{t('admin.back')}</button>
        <p role="alert" className={errorClass}>{t('admin.loadError')}</p>
      </div>
    )
  }
  if (!detail || !registration) return <p className={mutedClass}>{t('common.loading')}</p>

  function applyMutation(result: BookingMutation, kind: 'updated' | 'cancelled') {
    setDetail(result.booking)
    setEditing(false)
    setOutcome({ kind, emailSent: result.email_sent })
    onChanged()
  }

  const allDay = t('picker.allDay')
  const confirmed = detail.status === 'confirmed'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={onBack} className={secondaryButtonClass}>{t('admin.back')}</button>
        <h3 className="text-lg font-semibold">{detail.name}</h3>
        {statusBadge(detail.status, t(`admin.status.${detail.status}`))}
      </div>

      {outcome && (
        <p role="status" className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-950">
          <span className="font-medium">{outcome.kind === 'cancelled' ? t('admin.result.cancelled') : t('admin.result.saved')}</span>{' '}
          <EmailResult sent={outcome.emailSent} />
        </p>
      )}

      <div className={cardClass}>
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className={mutedClass}>{t('admin.columns.slot')}</dt>
          <dd className="font-medium">{formatSlot(detail.slot_date, detail.slot_time, i18n.language, allDay)}</dd>
          <dt className={mutedClass}>{t('admin.columns.email')}</dt>
          <dd className="break-all">{detail.email}</dd>
          <dt className={mutedClass}>{t('admin.detail.language')}</dt>
          <dd>{detail.language || '–'}</dd>
          <dt className={mutedClass}>{t('admin.detail.account')}</dt>
          <dd>{detail.user_sub ? t('admin.detail.signedIn') : t('admin.detail.anonymous')}</dd>
          <dt className={mutedClass}>{t('admin.columns.created')}</dt>
          <dd>{formatDateTime(detail.created_at, i18n.language)}</dd>
          <dt className={mutedClass}>{t('admin.detail.consent')}</dt>
          <dd>{formatDateTime(detail.consent_at, i18n.language)}</dd>
          {detail.cancelled_at && (
            <>
              <dt className={mutedClass}>{t('admin.detail.cancelledAt')}</dt>
              <dd>{formatDateTime(detail.cancelled_at, i18n.language)}</dd>
            </>
          )}
        </dl>
      </div>

      <div>
        <h4 className="mb-2 font-semibold">{t('admin.detail.answers')}</h4>
        {detail.answers.length === 0 ? (
          <p className={mutedClass}>{t('admin.detail.noAnswers')}</p>
        ) : (
          <SubmissionView submission={{ id: detail.id, form_id: registration.form_id, created_at: detail.created_at, answers: detail.answers }} />
        )}
      </div>

      {confirmed ? (
        <>
          {editing ? (
            <EditBooking
              registration={registration}
              detail={detail}
              questions={questions}
              onCancel={() => setEditing(false)}
              onSaved={(result) => applyMutation(result, 'updated')}
            />
          ) : (
            <button type="button" onClick={() => setEditing(true)} className={primaryButtonClass}>{t('admin.edit.open')}</button>
          )}
          <CancelBooking detail={detail} onCancelled={(result) => applyMutation(result, 'cancelled')} />
        </>
      ) : (
        <p className={mutedClass}>{t('admin.detail.cancelledNoEdit')}</p>
      )}

      <div>
        <h4 className="mb-2 font-semibold">{t('admin.history.title')}</h4>
        <History history={detail.history} />
      </div>
    </div>
  )
}

function EmailResult({ sent }: { sent: boolean | null }) {
  const { t } = useTranslation('event_booking')
  if (sent === null) return <span>{t('admin.result.notAsked')}</span>
  return sent ? <span className={okClass}>{t('admin.result.sent')}</span> : <span className={errorClass}>{t('admin.result.failed')}</span>
}

function NotifyFields({
  note,
  onNote,
  notify,
  onNotify,
  idPrefix,
  disabled,
}: {
  note: string
  onNote: (value: string) => void
  notify: boolean
  onNotify: (value: boolean) => void
  idPrefix: string
  disabled: boolean
}) {
  const { t } = useTranslation('event_booking')
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor={`${idPrefix}-note`} className={labelClass}>{t('admin.note.label')}</label>
        <textarea id={`${idPrefix}-note`} rows={3} maxLength={1000} value={note} onChange={(e) => onNote(e.target.value)} disabled={disabled} className={inputClass} />
        <p className={`mt-1 ${mutedClass}`}>{t('admin.note.hint')}</p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={notify} onChange={(e) => onNotify(e.target.checked)} disabled={disabled} className="mt-1" />
        <span>{t('admin.note.notify')}</span>
      </label>
    </div>
  )
}

function EditBooking({
  registration,
  detail,
  questions,
  onCancel,
  onSaved,
}: {
  registration: RegistrationAdmin
  detail: BookingDetail
  questions: Question[]
  onCancel: () => void
  onSaved: (result: BookingMutation) => void
}) {
  const { t } = useTranslation('event_booking')
  const [slot, setSlot] = useState<SlotChoice | null>({ date: detail.slot_date, time: detail.slot_time })
  const [name, setName] = useState(detail.name)
  const [email, setEmail] = useState(detail.email)
  const [values, setValues] = useState<FormValues>(() => valuesFromAnswers(detail.answers))
  const [note, setNote] = useState('')
  const [notify, setNotify] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string | string[]>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const finiteDays = registration.blocks.length > 0 && registration.blocks.every((block) => block.days_mode === 'dates')
  const loadDays = useCallback(
    (month?: string) => {
      const params = new URLSearchParams({ booking_id: detail.id })
      if (month) params.set('month', month)
      return fetchJson<{ days: FreeDay[] }>(`${API_BASE}/manage/registrations/${registration.id}/days?${params}`).then((r) => r.days)
    },
    [registration.id, detail.id],
  )
  const loadSlots = useCallback(
    (date: string) => {
      const params = new URLSearchParams({ booking_id: detail.id, date })
      return fetchJson<{ slots: SlotInfo[] }>(`${API_BASE}/manage/registrations/${registration.id}/slots?${params}`).then((r) => r.slots)
    },
    [registration.id, detail.id],
  )

  function messageFor(field: string, code: string): string {
    const key = FIELD_ERROR_KEYS[`${field}:${code}`]
    return key ? t(key) : t('admin.errors.unknown', { code })
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setErrors({})
    setGeneral(null)
    if (!slot) {
      setErrors({ slot: 'incomplete' })
      return
    }
    setSaving(true)
    try {
      const result = await sendJson<BookingMutation>(`${API_BASE}/manage/bookings/${detail.id}`, 'PATCH', {
        slot_date: slot.date,
        slot_time: slot.time ? slot.time.slice(0, 5) : null,
        name,
        email,
        answers: collectAnswers(questions, values),
        note: note.trim() || null,
        notify,
      })
      onSaved(result)
    } catch (err) {
      const found = errorsOf(err)
      if (statusOf(err) === 409 && found.slot === 'full') {
        setErrors({ slot: 'full' })
        setSlot(null)
        setReloadKey((key) => key + 1)
      } else if ((statusOf(err) === 422 || statusOf(err) === 409) && Object.keys(found).length > 0) {
        setErrors(found)
      } else {
        setGeneral(t('admin.errors.generic'))
      }
    } finally {
      setSaving(false)
    }
  }

  const slotError = errors.slot ? (errors.slot === 'incomplete' ? t('admin.errors.slotIncomplete') : messageFor('slot', String(errors.slot))) : null
  const formError = typeof errors._form === 'string' ? messageFor('_form', errors._form) : null
  const fieldError = (field: string) => (typeof errors[field] === 'string' ? messageFor(field, errors[field] as string) : null)
  const idPrefix = `edit-${detail.id}`

  return (
    <form onSubmit={save} className={`${cardClass} space-y-4`} aria-label={t('admin.edit.title')}>
      <h4 className="font-semibold">{t('admin.edit.title')}</h4>
      <SlotPicker
        finiteDays={finiteDays}
        maxDaysAhead={ADMIN_HORIZON_DAYS}
        loadDays={loadDays}
        loadSlots={loadSlots}
        value={slot}
        onChange={setSlot}
        disabled={saving}
        error={slotError}
        idPrefix={idPrefix}
        reloadKey={reloadKey}
      />
      <p className={mutedClass}>{t('admin.edit.capacityHint')}</p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${idPrefix}-name`} className={labelClass}>{t('form.name')}</label>
          <input id={`${idPrefix}-name`} type="text" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} disabled={saving} aria-invalid={fieldError('name') ? true : undefined} className={inputClass} />
          {fieldError('name') && <p role="alert" className={`mt-1 ${errorClass}`}>{fieldError('name')}</p>}
        </div>
        <div>
          <label htmlFor={`${idPrefix}-email`} className={labelClass}>{t('form.email')}</label>
          <input id={`${idPrefix}-email`} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} disabled={saving} aria-invalid={fieldError('email') ? true : undefined} className={inputClass} />
          {fieldError('email') && <p role="alert" className={`mt-1 ${errorClass}`}>{fieldError('email')}</p>}
        </div>
      </div>

      {questions.length > 0 && (
        <FormRenderer questions={questions} values={values} onChange={setValues} errors={stringErrors(errors)} disabled={saving} idPrefix={idPrefix} />
      )}

      <NotifyFields note={note} onNote={setNote} notify={notify} onNotify={setNotify} idPrefix={idPrefix} disabled={saving} />

      {(general || formError) && <p role="alert" className={errorClass}>{general ?? formError}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className={primaryButtonClass}>{saving ? t('admin.edit.saving') : t('admin.edit.save')}</button>
        <button type="button" onClick={onCancel} disabled={saving} className={secondaryButtonClass}>{t('admin.edit.discard')}</button>
      </div>
    </form>
  )
}

function CancelBooking({ detail, onCancelled }: { detail: BookingDetail; onCancelled: (result: BookingMutation) => void }) {
  const { t } = useTranslation('event_booking')
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [notify, setNotify] = useState(true)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  async function cancel() {
    if (!window.confirm(t('admin.cancel.confirm'))) return
    setBusy(true)
    setFailed(false)
    try {
      onCancelled(await sendJson<BookingMutation>(`${API_BASE}/manage/bookings/${detail.id}/cancel`, 'POST', { note: note.trim() || null, notify }))
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div>
        <button type="button" onClick={() => setOpen(true)} className={dangerButtonClass}>{t('admin.cancel.open')}</button>
      </div>
    )
  }
  return (
    <div className={`${cardClass} space-y-3`}>
      <h4 className="font-semibold">{t('admin.cancel.title')}</h4>
      <p className={mutedClass}>{t('admin.cancel.hint')}</p>
      <NotifyFields note={note} onNote={setNote} notify={notify} onNotify={setNotify} idPrefix={`cancel-${detail.id}`} disabled={busy} />
      {failed && <p role="alert" className={errorClass}>{t('admin.errors.generic')}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={cancel} disabled={busy} className={dangerButtonClass}>{busy ? t('admin.cancel.cancelling') : t('admin.cancel.button')}</button>
        <button type="button" onClick={() => setOpen(false)} disabled={busy} className={secondaryButtonClass}>{t('admin.cancel.keep')}</button>
      </div>
    </div>
  )
}
