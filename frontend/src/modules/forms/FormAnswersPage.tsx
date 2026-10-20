/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, fetchJson, type FormDefinition, type FormStatsData, type Submission, type SubmissionPage } from './api'
import FormStats from './FormStats'
import SubmissionList from './SubmissionList'
import SubmissionView from './SubmissionView'
import { FormsGate, PageMessage, secondaryButtonClass } from './ui'

const PAGE_SIZE = 20

type Tab = 'answers' | 'stats'

function Answers({ formId }: { formId: string }) {
  const { t } = useTranslation('forms')
  const [form, setForm] = useState<FormDefinition | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [tab, setTab] = useState<Tab>('answers')
  const [items, setItems] = useState<Submission[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [selected, setSelected] = useState<Submission | null>(null)
  const [stats, setStats] = useState<FormStatsData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchJson<FormDefinition>(`${API_BASE}/manage/${formId}`)
      .then((f) => !cancelled && setForm(f))
      .catch((err) => !cancelled && ((err as { status?: number }).status === 404 ? setNotFound(true) : setError(true)))
    fetchJson<SubmissionPage>(`${API_BASE}/manage/${formId}/submissions?limit=${PAGE_SIZE}`)
      .then((page) => {
        if (cancelled) return
        setItems(page.items)
        setHasMore(page.has_more)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [formId])

  // The summary is fetched when its tab is first opened - and again on every return, so it is never stale.
  useEffect(() => {
    if (tab !== 'stats') return
    let cancelled = false
    fetchJson<FormStatsData>(`${API_BASE}/manage/${formId}/stats`)
      .then((s) => !cancelled && setStats(s))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [formId, tab])

  const loadMore = useCallback(async () => {
    if (!items) return
    setLoadingMore(true)
    try {
      const page = await fetchJson<SubmissionPage>(`${API_BASE}/manage/${formId}/submissions?limit=${PAGE_SIZE}&offset=${items.length}`)
      setItems([...items, ...page.items])
      setHasMore(page.has_more)
    } catch {
      setError(true)
    } finally {
      setLoadingMore(false)
    }
  }, [formId, items])

  if (notFound) return <PageMessage>{t('answers.notFound')}</PageMessage>

  const tabs: { key: Tab; label: string }[] = [
    { key: 'answers', label: t('answers.tabAnswers') },
    { key: 'stats', label: t('answers.tabStats') },
  ]

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <h1 className="mb-1 text-3xl font-semibold tracking-tight">{t('answers.title')}</h1>
      <p className="mb-6 text-slate-600 dark:text-slate-400">{form ? form.name : '…'}</p>

      <div role="tablist" aria-label={t('answers.title')} className="mb-6 flex gap-2 border-b border-slate-200 dark:border-slate-800">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`forms-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`forms-panel-${key}`}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === key ? 'border-slate-900 dark:border-slate-100' : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="mb-4 text-sm text-red-600 dark:text-red-400">{t('answers.loadError')}</p>}

      <div role="tabpanel" id="forms-panel-answers" aria-labelledby="forms-tab-answers" hidden={tab !== 'answers'}>
        {selected ? (
          <div className="space-y-4">
            <button type="button" onClick={() => setSelected(null)} className={secondaryButtonClass}>
              ← {t('answers.backToList')}
            </button>
            <SubmissionView submission={selected} />
          </div>
        ) : items === null ? (
          !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
        ) : (
          <SubmissionList submissions={items} onOpen={setSelected} hasMore={hasMore} onLoadMore={loadMore} loadingMore={loadingMore} />
        )}
      </div>

      <div role="tabpanel" id="forms-panel-stats" aria-labelledby="forms-tab-stats" hidden={tab !== 'stats'}>
        {stats === null ? !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p> : <FormStats stats={stats} />}
      </div>
    </div>
  )
}

/** /forms/manage/:formId - every answer of a form and a summary, for administrators. The module has no list of forms: other modules link here with their form's id. */
export default function FormAnswersPage() {
  const { t } = useTranslation('forms')
  const { formId } = useParams<{ formId: string }>()
  usePageMeta({ title: t('answers.title') })
  return <FormsGate>{formId && <Answers key={formId} formId={formId} />}</FormsGate>
}
