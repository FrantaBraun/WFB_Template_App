/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import {
  errorStatus,
  fetchJson,
  fieldErrors,
  recordApi,
  recordPath,
  sendJson,
  tableApi,
  tablePath,
  type RefInfo,
  type RepoRecord,
  type TableDetail,
} from './api'
import AttributeField, { type FieldContext } from './fields'
import { buildData, initialDrafts, type DraftValue, type Drafts } from './recordForm'
import SlugField, { type SlugStatus } from './SlugField'
import { BackLink, PageMessage, cardClass, errorTextClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useSaveErrorText } from './ui'

/**
 * /repository/:repo/table/:table/item/new and .../item/:item/edit - the form
 * of a record, built from the table's attributes (see fields.tsx): a name, the
 * slug (made from the name until edited), and a control per attribute. The
 * server checks every value again and names what is wrong by attribute.
 */
export default function RecordFormPage() {
  const { t } = useTranslation('repository')
  const saveErrorText = useSaveErrorText()
  const navigate = useNavigate()
  const { table: tableSlug = '', item: itemSlug } = useParams()
  const { repository } = useRepositoryArea()
  const editing = itemSlug !== undefined

  const [table, setTable] = useState<TableDetail | null>(null)
  const [record, setRecord] = useState<RepoRecord | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [drafts, setDrafts] = useState<Drafts>({})
  const [refs, setRefs] = useState<Record<string, RefInfo>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [slugStatus, setSlugStatus] = useState<SlugStatus>('idle')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  usePageMeta({ title: editing ? t('record.form.editTitle') : t('record.form.newTitle'), noindex: true })

  useEffect(() => {
    let cancelled = false
    setTable(null)
    setRecord(null)
    setLoadError(null)
    Promise.all([
      fetchJson<TableDetail>(tableApi(repository.slug, tableSlug)),
      itemSlug ? fetchJson<RepoRecord>(recordApi(repository.slug, tableSlug, itemSlug)) : Promise.resolve(null),
    ])
      .then(([loadedTable, loadedRecord]) => {
        if (cancelled) return
        setTable(loadedTable)
        setRecord(loadedRecord)
        setDrafts(initialDrafts(loadedTable.attributes, loadedRecord?.data))
        if (loadedRecord) {
          setName(loadedRecord.name)
          setSlug(loadedRecord.slug)
          setRefs(loadedRecord.refs)
        }
      })
      .catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [repository.slug, tableSlug, itemSlug])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'record.notFound' : 'record.loadError')}</PageMessage>
  if (!table || (editing && !record)) return <PageMessage>{t('common.loading')}</PageMessage>

  const context: FieldContext = {
    refs,
    rememberRef: (id, info) => setRefs((current) => ({ ...current, [id]: info })),
  }
  const back = record ? recordPath(repository.slug, table.slug, record.slug) : tablePath(repository.slug, table.slug)
  const deleted = record?.deleted_on != null
  const canSave = name.trim() !== '' && slug !== '' && slugStatus !== 'bad' && !saving && !deleted

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!table) return
    const built = buildData(table.attributes, drafts)
    setErrors(built.errors)
    setError(null)
    if (Object.keys(built.errors).length > 0) {
      setError(t('record.form.fixErrors'))
      return
    }
    setSaving(true)
    const body = { name, slug, data: built.data }
    try {
      const saved = record
        ? await sendJson<RepoRecord>(recordApi(repository.slug, table.slug, record.slug), 'PATCH', body)
        : await sendJson<RepoRecord>(recordApi(repository.slug, table.slug), 'POST', body)
      navigate(recordPath(repository.slug, table.slug, saved.slug))
    } catch (err) {
      const server = fieldErrors(err)
      if (Object.keys(server).length > 0) {
        setErrors(server)
        setError(server.record === 'deleted' ? t('record.form.isDeleted') : t('record.form.fixErrors'))
      } else {
        setError(saveErrorText(err, 'record.form.saveError'))
      }
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <BackLink to={back}>{record ? record.name : table.name}</BackLink>
      <h1 className="text-3xl font-semibold tracking-tight">{editing ? t('record.form.editTitle') : t('record.form.newTitle', { table: table.name })}</h1>
      {deleted && <p className={errorTextClass}>{t('record.form.isDeleted')}</p>}

      <section className={`${cardClass} space-y-5 p-5`}>
        <div>
          <label htmlFor="record-name" className={labelClass}>
            {t('record.fields.name')} <span className="text-red-600 dark:text-red-400" aria-hidden="true">*</span>
          </label>
          <input id="record-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required aria-invalid={errors.name !== undefined} className={inputClass} />
          {errors.name && <p className={errorTextClass}>{t(`record.errors.${errors.name}`, { defaultValue: t('record.errors.generic') })}</p>}
        </div>
        <SlugField
          scope="record"
          repository={repository.slug}
          table={table.slug}
          name={name}
          value={slug}
          onChange={setSlug}
          currentSlug={record?.slug}
          autoFromName={!editing}
          onStatus={setSlugStatus}
          serverError={errors.slug ?? null}
        />
        {table.attributes.map((attribute) => (
          <AttributeField
            key={attribute.id}
            attribute={attribute}
            draft={drafts[attribute.id] ?? (attribute.type === 'list' || attribute.type === 'map' ? [] : '')}
            onChange={(draft: DraftValue) => setDrafts((current) => ({ ...current, [attribute.id]: draft }))}
            context={context}
            errors={errors}
          />
        ))}
      </section>

      {error && (
        <p className={errorTextClass} role="alert">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={!canSave} className={primaryButtonClass}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
        <button type="button" onClick={() => navigate(back)} className={secondaryButtonClass}>
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}
