/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BUCKETS,
  CHART_TYPES,
  DISPLAYS,
  FUNCTIONS,
  fieldErrors,
  sendJson,
  tableApi,
  type AggregateFunction,
  type Bucket,
  type ChartType,
  type Dimension,
  type SavedFilter,
  type Statistic,
  type StatisticBody,
  type StatisticDisplay,
  type StatisticResult,
  type TableDetail,
} from './api'
import StatisticView from './StatisticView'
import { Modal, errorTextClass, hintClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useSaveErrorText } from './ui'

const GROUPABLE_TYPES = ['text', 'boolean', 'number', 'date', 'datetime', 'reference']
const BUCKETED = new Set(['date', 'datetime', 'timestamp'])
const PREVIEW_DEBOUNCE_MS = 400

interface Option {
  key: string
  kind: string
  label?: string
}

/** The form of a statistic - what to group by (one or two dimensions), what to compute, over which saved filter, and how to show it - with a live preview of the result. */
export default function StatisticEditor({
  table,
  repositorySlug,
  filters,
  statistic,
  onSaved,
  onClose,
}: {
  table: TableDetail
  repositorySlug: string
  filters: SavedFilter[]
  statistic?: Statistic
  onSaved: () => void
  onClose: () => void
}) {
  const { t } = useTranslation('repository')
  const saveErrorText = useSaveErrorText()
  const dimensionOptions: Option[] = useMemo(
    () => [
      { key: 'created_on', kind: 'timestamp' },
      ...table.attributes.filter((attribute) => GROUPABLE_TYPES.includes(attribute.type)).map((attribute) => ({ key: attribute.id, kind: attribute.type, label: attribute.name })),
    ],
    [table.attributes],
  )
  const numberAttributes = table.attributes.filter((attribute) => attribute.type === 'number')
  const kindOf = (field: string) => dimensionOptions.find((option) => option.key === field)?.kind ?? 'text'
  const labelOf = (option: Option) => option.label ?? t('filters.system.createdOn')
  const dimensionFor = (field: string, bucket?: Bucket | null): Dimension => ({ field, bucket: BUCKETED.has(kindOf(field)) ? (bucket ?? 'month') : null })

  const [name, setName] = useState(statistic?.name ?? '')
  const [filterId, setFilterId] = useState(statistic?.filter_id ?? '')
  const [first, setFirst] = useState<Dimension>(statistic?.group_by[0] ?? dimensionFor(dimensionOptions[Math.min(1, dimensionOptions.length - 1)].key))
  const [second, setSecond] = useState<Dimension | null>(statistic?.group_by[1] ?? null)
  const [fn, setFn] = useState<AggregateFunction>(statistic?.aggregation.fn ?? 'count')
  const [aggregated, setAggregated] = useState(statistic?.aggregation.attribute_id ?? numberAttributes[0]?.id ?? '')
  const [display, setDisplay] = useState<StatisticDisplay>(statistic?.display ?? 'both')
  const [chartType, setChartType] = useState<ChartType>(statistic?.chart_type ?? 'bar')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ body: StatisticBody; result: StatisticResult } | null>(null)
  const [previewError, setPreviewError] = useState(false)

  const body: StatisticBody = useMemo(
    () => ({
      name: name.trim() || t('statistics.editor.untitled'),
      filter_id: filterId || null,
      group_by: second ? [first, second] : [first],
      aggregation: { fn, attribute_id: fn === 'count' ? null : aggregated || null },
      display,
      chart_type: second && chartType === 'pie' ? 'bar' : chartType,
    }),
    [name, filterId, first, second, fn, aggregated, display, chartType, t],
  )
  const bodyKey = JSON.stringify(body)

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      sendJson<StatisticResult>(`${tableApi(repositorySlug, table.slug)}/statistics-preview`, 'POST', JSON.parse(bodyKey))
        .then((result) => {
          if (cancelled) return
          setPreview({ body: JSON.parse(bodyKey), result })
          setPreviewError(false)
          setErrors({})
        })
        .catch((e) => {
          if (cancelled) return
          setPreviewError(true)
          setErrors(fieldErrors(e))
        })
    }, PREVIEW_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [bodyKey, repositorySlug, table.slug])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const path = `${tableApi(repositorySlug, table.slug)}/statistics`
      if (statistic) await sendJson<Statistic>(`${path}/${statistic.id}`, 'PUT', body)
      else await sendJson<Statistic>(path, 'POST', body)
      onSaved()
    } catch (err) {
      const server = fieldErrors(err)
      setErrors(server)
      setError(Object.keys(server).length ? t('statistics.editor.fixErrors') : saveErrorText(err, 'statistics.editor.saveError'))
      setSaving(false)
    }
  }

  function dimensionSelect(id: string, value: Dimension | null, onChange: (dimension: Dimension | null) => void, optional: boolean, errorKey: string) {
    const kind = value ? kindOf(value.field) : 'text'
    const code = errors[errorKey]
    return (
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-48">
          <label htmlFor={id} className={labelClass}>
            {t(optional ? 'statistics.editor.thenBy' : 'statistics.editor.groupBy')}
          </label>
          <select
            id={id}
            value={value?.field ?? ''}
            onChange={(e) => onChange(e.target.value ? dimensionFor(e.target.value, value?.bucket) : null)}
            aria-invalid={code !== undefined}
            className={inputClass}
          >
            {optional && <option value="">{t('statistics.editor.noSecond')}</option>}
            {dimensionOptions.map((option) => (
              <option key={option.key} value={option.key}>
                {labelOf(option)}
              </option>
            ))}
          </select>
        </div>
        {value && BUCKETED.has(kind) && (
          <div>
            <label htmlFor={`${id}-bucket`} className={labelClass}>
              {t('statistics.editor.bucket')}
            </label>
            <select id={`${id}-bucket`} value={value.bucket ?? 'month'} onChange={(e) => onChange({ ...value, bucket: e.target.value as Bucket })} className={inputClass}>
              {BUCKETS.map((bucket) => (
                <option key={bucket} value={bucket}>
                  {t(`statistics.bucket.${bucket}`)}
                </option>
              ))}
            </select>
          </div>
        )}
        {code && <p className={`${errorTextClass} basis-full`}>{t(`statistics.errors.${code}`, { defaultValue: t('statistics.errors.generic') })}</p>}
      </div>
    )
  }

  return (
    <Modal title={t(statistic ? 'statistics.editor.editTitle' : 'statistics.editor.newTitle')} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="statistic-name" className={labelClass}>
            {t('statistics.editor.name')}
          </label>
          <input id="statistic-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required className={inputClass} />
        </div>

        <div>
          <label htmlFor="statistic-filter" className={labelClass}>
            {t('statistics.editor.filter')}
          </label>
          <select id="statistic-filter" value={filterId} onChange={(e) => setFilterId(e.target.value)} aria-invalid={errors.filter_id !== undefined} className={inputClass}>
            <option value="">{t('statistics.editor.allRecords')}</option>
            {filters.map((saved) => (
              <option key={saved.id} value={saved.id}>
                {saved.name}
              </option>
            ))}
          </select>
          {errors.filter_id && <p className={errorTextClass}>{t('statistics.errors.unknown_filter')}</p>}
        </div>

        {dimensionSelect('statistic-first', first, (dimension) => dimension && setFirst(dimension), false, 'group_by.0')}
        {dimensionSelect(
          'statistic-second',
          second,
          (dimension) => {
            setSecond(dimension)
            if (dimension && chartType === 'pie') setChartType('bar')
          },
          true,
          'group_by.1',
        )}

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="statistic-fn" className={labelClass}>
              {t('statistics.editor.compute')}
            </label>
            <select id="statistic-fn" value={fn} onChange={(e) => setFn(e.target.value as AggregateFunction)} className={inputClass}>
              {FUNCTIONS.map((candidate) => (
                <option key={candidate} value={candidate} disabled={candidate !== 'count' && numberAttributes.length === 0}>
                  {t(`statistics.editor.functions.${candidate}`)}
                </option>
              ))}
            </select>
          </div>
          {fn !== 'count' && (
            <div className="min-w-0 flex-1 basis-48">
              <label htmlFor="statistic-attribute" className={labelClass}>
                {t('statistics.editor.ofAttribute')}
              </label>
              <select id="statistic-attribute" value={aggregated} onChange={(e) => setAggregated(e.target.value)} aria-invalid={errors.aggregation !== undefined} className={inputClass}>
                {numberAttributes.map((attribute) => (
                  <option key={attribute.id} value={attribute.id}>
                    {attribute.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {errors.aggregation && <p className={`${errorTextClass} basis-full`}>{t(`statistics.errors.${errors.aggregation}`, { defaultValue: t('statistics.errors.generic') })}</p>}
        </div>
        {numberAttributes.length === 0 && <p className={hintClass}>{t('statistics.editor.noNumbers')}</p>}

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="statistic-display" className={labelClass}>
              {t('statistics.editor.display')}
            </label>
            <select id="statistic-display" value={display} onChange={(e) => setDisplay(e.target.value as StatisticDisplay)} className={inputClass}>
              {DISPLAYS.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {t(`statistics.display.${candidate}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="statistic-chart" className={labelClass}>
              {t('statistics.editor.chartType')}
            </label>
            <select id="statistic-chart" value={body.chart_type} onChange={(e) => setChartType(e.target.value as ChartType)} className={inputClass}>
              {CHART_TYPES.map((candidate) => (
                <option key={candidate} value={candidate} disabled={candidate === 'pie' && second !== null}>
                  {t(`statistics.chart.${candidate}`)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <section aria-label={t('statistics.editor.preview')} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
          <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">{t('statistics.editor.preview')}</h3>
          <div className={previewError ? 'opacity-50' : ''}>
            {preview ? (
              <StatisticView
                result={preview.result}
                dimensions={preview.body.group_by}
                aggregation={preview.body.aggregation}
                attributes={table.attributes}
                display={preview.body.display === 'hidden' ? 'both' : preview.body.display}
                chartType={preview.body.chart_type}
              />
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
            )}
          </div>
          {previewError && <p className={errorTextClass}>{t('statistics.editor.previewError')}</p>}
        </section>

        {error && <p className={errorTextClass}>{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            {t('common.cancel')}
          </button>
          <button type="submit" disabled={saving || name.trim() === '' || previewError} className={primaryButtonClass}>
            {saving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
