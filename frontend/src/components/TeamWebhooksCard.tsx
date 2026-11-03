/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api/client'

/** A team's webhook as the backend shows it (WebhookOut) - the URL only ever masked. */
interface WebhookData {
  id: string
  kind: 'slack' | 'generic'
  name: string | null
  url_masked: string
  only_breaking: boolean
  enabled: boolean
  last_attempt_at: string | null
  last_status: 'ok' | 'error' | null
  last_error: string | null
  consecutive_failures: number
  created_at: string
}

const BUTTON =
  'rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800'
const INPUT =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'

function formatDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/**
 * A team's Slack channels and its own endpoints that hear about new versions
 * (backend /api/teams/:id/webhooks). Every member sees them, with the URL
 * masked - for Slack the URL is itself the right to post - but only an owner
 * can add, switch off, test or remove one (`isOwner` only decides what is
 * shown; the backend refuses anyone else). A generic webhook's signing secret
 * comes back once, when it is created, and is shown here until dismissed.
 * Server answers are English phrases, so the reasons the backend gives for a
 * refused URL or a failed delivery are mapped to translated texts here.
 */
export default function TeamWebhooksCard({ teamId, isOwner }: { teamId: string; isOwner: boolean }) {
  const { t, i18n } = useTranslation()
  const base = `/api/teams/${teamId}/webhooks`

  const [webhooks, setWebhooks] = useState<WebhookData[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, string>>({})

  const [kind, setKind] = useState<'slack' | 'generic'>('slack')
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [onlyBreaking, setOnlyBreaking] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [secret, setSecret] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const resp = await apiFetch(base)
      if (!resp.ok) throw new Error()
      setWebhooks(await resp.json())
      setLoadError(null)
    } catch {
      setLoadError(t('teams.detail.webhooks.loadError'))
    }
  }, [base, t])

  useEffect(() => {
    load()
  }, [load])

  /** The reason a URL was refused (an English phrase from the backend), in the user's language. */
  function urlErrorText(status: number, detail: unknown): string {
    if (status === 409) return t('teams.detail.webhooks.errors.limit')
    const text = typeof detail === 'string' ? detail : ''
    if (text.includes('hooks.slack.com')) return t('teams.detail.webhooks.errors.notSlack')
    if (text.includes('https://')) return t('teams.detail.webhooks.errors.notHttps')
    if (text.includes('user name or password')) return t('teams.detail.webhooks.errors.credentials')
    if (text.includes('cannot be resolved')) return t('teams.detail.webhooks.errors.unresolved')
    if (text.includes('not a public one')) return t('teams.detail.webhooks.errors.notPublic')
    return t('teams.detail.webhooks.errors.invalid')
  }

  /** How a delivery failed (the backend's short fixed phrase), in the user's language. */
  function deliveryErrorText(error: string | null): string {
    if (error === 'Timed out') return t('teams.detail.webhooks.delivery.timedOut')
    if (error === 'Could not connect') return t('teams.detail.webhooks.delivery.connect')
    if (error === 'The address is not allowed') return t('teams.detail.webhooks.delivery.notAllowed')
    const answered = error?.match(/^The receiver answered (\d+)$/)
    if (answered) return t('teams.detail.webhooks.delivery.answered', { status: answered[1] })
    return t('teams.detail.webhooks.delivery.unexpected')
  }

  async function handleAdd(e: FormEvent) {
    e.preventDefault()
    setAdding(true)
    setAddError(null)
    try {
      const resp = await apiFetch(base, {
        method: 'POST',
        body: JSON.stringify({ kind, url: url.trim(), name: name.trim() || null, only_breaking: onlyBreaking }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        setAddError(resp.status === 422 || resp.status === 409 ? urlErrorText(resp.status, body.detail) : t('teams.detail.webhooks.add.error'))
        return
      }
      const created: { secret: string | null } = await resp.json()
      setSecret(created.secret)
      setUrl('')
      setName('')
      setOnlyBreaking(false)
      await load()
    } catch {
      setAddError(t('teams.detail.webhooks.add.error'))
    } finally {
      setAdding(false)
    }
  }

  async function change(webhook: WebhookData, patch: Partial<Pick<WebhookData, 'enabled' | 'only_breaking'>>) {
    setBusyId(webhook.id)
    setActionError(null)
    try {
      const resp = await apiFetch(`${base}/${webhook.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
      if (!resp.ok) throw new Error()
      await load()
    } catch {
      setActionError(t('teams.detail.webhooks.actionError'))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(webhook: WebhookData) {
    if (!window.confirm(t('teams.detail.webhooks.confirmDelete'))) return
    setBusyId(webhook.id)
    setActionError(null)
    try {
      const resp = await apiFetch(`${base}/${webhook.id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error()
      await load()
    } catch {
      setActionError(t('teams.detail.webhooks.actionError'))
    } finally {
      setBusyId(null)
    }
  }

  async function test(webhook: WebhookData) {
    setBusyId(webhook.id)
    setActionError(null)
    try {
      const resp = await apiFetch(`${base}/${webhook.id}/test`, { method: 'POST' })
      if (!resp.ok) throw new Error()
      const result: { ok: boolean; error: string | null } = await resp.json()
      setTestResults((prev) => ({
        ...prev,
        [webhook.id]: result.ok
          ? t('teams.detail.webhooks.testOk')
          : t('teams.detail.webhooks.testFailed', { error: deliveryErrorText(result.error) }),
      }))
      await load()
    } catch {
      setActionError(t('teams.detail.webhooks.actionError'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.detail.webhooks.title')}
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">{t('teams.detail.webhooks.description')}</p>
        {!isOwner && <p className="text-sm text-slate-500 dark:text-slate-400">{t('teams.detail.webhooks.ownersOnly')}</p>}
      </div>

      {secret && (
        <div role="alert" className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <p className="font-medium">{t('teams.detail.webhooks.secret.title')}</p>
          <input
            readOnly
            value={secret}
            onFocus={(e) => e.target.select()}
            aria-label={t('teams.detail.webhooks.secret.title')}
            className="w-full rounded-lg border border-amber-300 bg-white px-3 py-1.5 font-mono text-xs text-slate-900 dark:border-amber-700 dark:bg-slate-950 dark:text-slate-100"
          />
          <p>{t('teams.detail.webhooks.secret.body')}</p>
          <button type="button" onClick={() => setSecret(null)} className={BUTTON}>
            {t('teams.detail.webhooks.secret.dismiss')}
          </button>
        </div>
      )}

      {loadError && <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>}
      {actionError && <p className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}
      {webhooks && webhooks.length === 0 && <p className="text-sm text-slate-600 dark:text-slate-400">{t('teams.detail.webhooks.empty')}</p>}

      {webhooks && webhooks.length > 0 && (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {webhooks.map((webhook) => (
            <li key={webhook.id} className="space-y-2 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  {t(`teams.detail.webhooks.kind.${webhook.kind}`)}
                </span>
                {webhook.name && <span className="font-medium text-slate-900 dark:text-slate-100">{webhook.name}</span>}
                <span className="break-all font-mono text-xs text-slate-500 dark:text-slate-400">{webhook.url_masked}</span>
                {webhook.only_breaking && (
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/40 dark:text-red-300">
                    {t('teams.detail.webhooks.onlyBreaking')}
                  </span>
                )}
                {!webhook.enabled && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                    {t('teams.detail.webhooks.disabled')}
                  </span>
                )}
              </div>

              <p className={`text-xs ${webhook.last_status === 'error' ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`}>
                {webhook.last_status === null
                  ? t('teams.detail.webhooks.neverUsed')
                  : webhook.last_status === 'ok'
                    ? t('teams.detail.webhooks.statusOk')
                    : t('teams.detail.webhooks.statusError', { error: deliveryErrorText(webhook.last_error) })}
                {webhook.last_attempt_at && ` · ${formatDateTime(webhook.last_attempt_at, i18n.language)}`}
                {webhook.consecutive_failures > 1 && ` · ${t('teams.detail.webhooks.failures', { count: webhook.consecutive_failures })}`}
              </p>
              {testResults[webhook.id] && <p role="status" className="text-xs text-slate-700 dark:text-slate-300">{testResults[webhook.id]}</p>}

              {isOwner && (
                <div className="flex flex-wrap items-center gap-2">
                  <button type="button" disabled={busyId === webhook.id} onClick={() => test(webhook)} className={BUTTON}>
                    {busyId === webhook.id ? t('teams.detail.webhooks.testing') : t('teams.detail.webhooks.test')}
                  </button>
                  <button type="button" disabled={busyId === webhook.id} onClick={() => change(webhook, { enabled: !webhook.enabled })} className={BUTTON}>
                    {webhook.enabled ? t('teams.detail.webhooks.disable') : t('teams.detail.webhooks.enable')}
                  </button>
                  <button type="button" disabled={busyId === webhook.id} onClick={() => change(webhook, { only_breaking: !webhook.only_breaking })} className={BUTTON}>
                    {webhook.only_breaking ? t('teams.detail.webhooks.allChanges') : t('teams.detail.webhooks.onlyBreakingAction')}
                  </button>
                  <button type="button" disabled={busyId === webhook.id} onClick={() => remove(webhook)} className={BUTTON}>
                    {t('teams.detail.webhooks.delete')}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {isOwner && (
        <form onSubmit={handleAdd} className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">{t('teams.detail.webhooks.add.title')}</h3>
          <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
            <div>
              <label htmlFor="webhook-kind" className="mb-1 block text-xs text-slate-600 dark:text-slate-400">
                {t('teams.detail.webhooks.add.kind')}
              </label>
              <select id="webhook-kind" value={kind} onChange={(e) => setKind(e.target.value as 'slack' | 'generic')} className={INPUT}>
                <option value="slack">{t('teams.detail.webhooks.kind.slack')}</option>
                <option value="generic">{t('teams.detail.webhooks.kind.generic')}</option>
              </select>
            </div>
            <div>
              <label htmlFor="webhook-url" className="mb-1 block text-xs text-slate-600 dark:text-slate-400">
                {t('teams.detail.webhooks.add.url')}
              </label>
              <input id="webhook-url" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className={INPUT} />
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {t(kind === 'slack' ? 'teams.detail.webhooks.add.urlHelpSlack' : 'teams.detail.webhooks.add.urlHelpGeneric')}
              </p>
            </div>
          </div>
          <div>
            <label htmlFor="webhook-name" className="mb-1 block text-xs text-slate-600 dark:text-slate-400">
              {t('teams.detail.webhooks.add.name')}
            </label>
            <input id="webhook-name" type="text" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={onlyBreaking}
              onChange={(e) => setOnlyBreaking(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 dark:border-slate-700"
            />
            {t('teams.detail.webhooks.add.onlyBreaking')}
          </label>
          {addError && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {addError}
            </p>
          )}
          <button
            type="submit"
            disabled={adding || !url.trim()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {adding ? t('teams.detail.webhooks.add.saving') : t('teams.detail.webhooks.add.submit')}
          </button>
        </form>
      )}
    </div>
  )
}
