/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import AttributeEditor, {
  draftFromAttribute,
  draftProblems,
  draftsToRequest,
  type AttributeDraft,
} from './AttributeEditor'
import {
  detailField,
  errorStatus,
  fetchJson,
  fieldErrors,
  repositoryApi,
  repositoryPath,
  sendJson,
  tableApi,
  tablePath,
  type TableDetail,
} from './api'
import SlugField, { type SlugStatus } from './SlugField'
import {
  BackLink,
  Modal,
  PageMessage,
  cardClass,
  errorTextClass,
  inputClass,
  labelClass,
  primaryButtonClass,
  secondaryButtonClass,
  useSaveErrorText,
} from './ui'

const MAX_ATTRIBUTES = 50

interface PurgeRequired {
  id: string
  name: string
  record_count: number
}

interface Loaded {
  table: TableDetail
}

/**
 * /repository/:repo/table/new and /repository/:repo/table/:table/edit - the
 * definition of a table: name, description, slug, how it is shown (table or
 * grid) and its attributes. Saving an edit that removes an attribute records
 * hold values for first asks to confirm, with how many records are affected.
 */
export default function TableFormPage() {
  const { t } = useTranslation('repository')
  const saveErrorText = useSaveErrorText()
  const navigate = useNavigate()
  const location = useLocation()
  const { table: tableSlug } = useParams()
  const { repository, reload } = useRepositoryArea()
  const editing = tableSlug !== undefined

  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [slug, setSlug] = useState('')
  const [viewType, setViewType] = useState<'table' | 'grid'>('table')
  const [drafts, setDrafts] = useState<AttributeDraft[]>([])
  const [slugStatus, setSlugStatus] = useState<SlugStatus>('idle')
  const [slugError, setSlugError] = useState<string | null>(null)
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({})
  const [showProblems, setShowProblems] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [purge, setPurge] = useState<PurgeRequired[] | null>(null)
  const notice = (location.state as { notice?: string } | null)?.notice

  usePageMeta({ title: editing ? t('table.form.editTitle') : t('table.form.newTitle'), noindex: true })

  useEffect(() => {
    if (!tableSlug) return
    let cancelled = false
    setLoaded(null)
    setLoadError(null)
    fetchJson<TableDetail>(tableApi(repository.slug, tableSlug))
      .then((table) => {
        if (cancelled) return
        setLoaded({ table })
        setName(table.name)
        setDescription(table.description)
        setSlug(table.slug)
        setViewType(table.view_type)
        setDrafts(table.attributes.map(draftFromAttribute))
      })
      .catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [repository.slug, tableSlug])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'table.notFound' : 'table.loadError')}</PageMessage>
  if (editing && !loaded) return <PageMessage>{t('common.loading')}</PageMessage>

  const problems = draftProblems(drafts)
  const hasProblems = Object.keys(problems).length > 0
  const canSave = name.trim() !== '' && slug !== '' && slugStatus !== 'bad' && !saving

  async function saveAttributes(targetSlug: string, confirmPurge: boolean): Promise<TableDetail> {
    return sendJson<TableDetail>(
      `${tableApi(repository.slug, targetSlug)}/attributes${confirmPurge ? '?confirm_purge=true' : ''}`,
      'PUT',
      { attributes: draftsToRequest(drafts) },
    )
  }

  function reportTableError(err: unknown) {
    const errors = fieldErrors(err)
    if (errors.slug) setSlugError(errors.slug)
    else setError(saveErrorText(err, 'table.form.saveError'))
    setSaving(false)
  }

  async function submit(e?: FormEvent, confirmPurge = false) {
    e?.preventDefault()
    setShowProblems(true)
    if (hasProblems) return
    setSaving(true)
    setError(null)
    setSlugError(null)
    setServerErrors({})
    let savedSlug = tableSlug as string

    if (editing) {
      // Attributes first, under the slug the table has now: a removed attribute that
      // records hold values for must be confirmed before anything else is changed.
      try {
        await saveAttributes(savedSlug, confirmPurge)
      } catch (err) {
        setSaving(false)
        const needed = detailField<PurgeRequired[]>(err, 'purge_required')
        if (needed?.length) {
          setPurge(needed)
          return
        }
        setServerErrors(fieldErrors(err))
        setError(saveErrorText(err, 'table.form.attributesError'))
        return
      }
      try {
        savedSlug = (await sendJson<TableDetail>(tableApi(repository.slug, savedSlug), 'PATCH', { name, description, slug, view_type: viewType })).slug
      } catch (err) {
        reportTableError(err)
        return
      }
    } else {
      try {
        savedSlug = (await sendJson<TableDetail>(`${repositoryApi(repository.slug)}/tables`, 'POST', { name, description, slug, view_type: viewType })).slug
      } catch (err) {
        reportTableError(err)
        return
      }
      if (drafts.length > 0) {
        try {
          await saveAttributes(savedSlug, false)
        } catch {
          // The table exists now: carry on from its edit page, not a second "create".
          await reload()
          navigate(`${repositoryPath(repository.slug)}/table/${savedSlug}/edit`, { replace: true, state: { notice: 'attributesFailed' } })
          return
        }
      }
    }
    await reload()
    navigate(tablePath(repository.slug, savedSlug as string))
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <BackLink to={editing && tableSlug ? tablePath(repository.slug, tableSlug) : repositoryPath(repository.slug)}>
        {editing ? loaded?.table.name : repository.name}
      </BackLink>
      <h1 className="text-3xl font-semibold tracking-tight">{editing ? t('table.form.editTitle') : t('table.form.newTitle')}</h1>
      {notice === 'attributesFailed' && <p className={errorTextClass}>{t('table.form.attributesFailedNotice')}</p>}

      <section className={`${cardClass} space-y-5 p-5`}>
        <div>
          <label htmlFor="table-name" className={labelClass}>
            {t('table.fields.name')}
          </label>
          <input id="table-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required className={inputClass} />
        </div>
        <div>
          <label htmlFor="table-description" className={labelClass}>
            {t('table.fields.description')}
          </label>
          <textarea id="table-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={3} className={inputClass} />
        </div>
        <SlugField
          scope="table"
          repository={repository.slug}
          name={name}
          value={slug}
          onChange={setSlug}
          currentSlug={loaded?.table.slug}
          autoFromName={!editing}
          onStatus={setSlugStatus}
          serverError={slugError}
        />
        <fieldset>
          <legend className={labelClass}>{t('table.fields.viewType')}</legend>
          <div className="flex flex-wrap gap-4 text-sm text-slate-800 dark:text-slate-200">
            {(['table', 'grid'] as const).map((type) => (
              <label key={type} className="flex items-center gap-2">
                <input type="radio" name="view_type" value={type} checked={viewType === type} onChange={() => setViewType(type)} className="repo-check" />
                {t(`table.view.${type}`)}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <AttributeEditor
        drafts={drafts}
        onChange={setDrafts}
        tables={repository.tables}
        selfTableId={loaded?.table.id}
        problems={showProblems ? problems : {}}
        serverErrors={serverErrors}
        maxAttributes={MAX_ATTRIBUTES}
      />

      {error && <p className={errorTextClass}>{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={!canSave} className={primaryButtonClass}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
        <button
          type="button"
          onClick={() => navigate(editing && tableSlug ? tablePath(repository.slug, tableSlug) : repositoryPath(repository.slug))}
          className={secondaryButtonClass}
        >
          {t('common.cancel')}
        </button>
      </div>

      {purge && (
        <Modal title={t('table.form.purgeTitle')} onClose={() => setPurge(null)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-700 dark:text-slate-300">{t('table.form.purgeMessage')}</p>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {purge.map((item) => (
                <li key={item.id}>{t('table.form.purgeItem', { name: item.name, count: item.record_count })}</li>
              ))}
            </ul>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setPurge(null)} className={secondaryButtonClass}>
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setPurge(null)
                  void submit(undefined, true)
                }}
                className="inline-flex items-center justify-center rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800"
              >
                {t('table.form.purgeConfirm')}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </form>
  )
}
