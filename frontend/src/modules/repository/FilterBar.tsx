/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ReferencePicker } from './references'
import { OPERATORS, newCondition, operatorNeedsTwoValues, operatorNeedsValue, type ConditionDraft, type FieldInfo } from './filterModel'
import { inputClass, secondaryButtonClass } from './ui'

const SYSTEM_LABELS: Record<string, string> = { name: 'name', slug: 'slug', created_on: 'createdOn' }

export function useFieldLabel() {
  const { t } = useTranslation('repository')
  return (field: FieldInfo): string => field.label ?? t(`filters.system.${SYSTEM_LABELS[field.key]}`)
}

/** The input for the value of one filter row, by the kind of the field. */
function ValueInput({
  field,
  value,
  onChange,
  label,
  refName,
  onPick,
}: {
  field: FieldInfo
  value: string
  onChange: (value: string) => void
  label: string
  refName?: string
  onPick: () => void
}) {
  const { t } = useTranslation('repository')
  switch (field.kind) {
    case 'number':
      return <input type="number" step="any" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label} className={`${inputClass} w-36`} />
    case 'boolean':
      return (
        <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label} className={`${inputClass} w-28`}>
          <option value="">—</option>
          <option value="true">{t('record.boolean.yes')}</option>
          <option value="false">{t('record.boolean.no')}</option>
        </select>
      )
    case 'date':
    case 'timestamp':
      return <input type="date" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label} className={`${inputClass} w-44`} />
    case 'datetime':
      return <input type="datetime-local" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label} className={`${inputClass} w-52`} />
    case 'reference':
      return (
        <button type="button" onClick={onPick} aria-label={label} className={`${secondaryButtonClass} max-w-[14rem]`}>
          <span className="truncate">{value ? (refName ?? '…') : t('reference.choose')}</span>
        </button>
      )
    default:
      return <input value={value} onChange={(e) => onChange(e.target.value)} maxLength={200} aria-label={label} className={`${inputClass} w-48`} />
  }
}

/**
 * The filter of the content page: a quick search, filter rows (a field, an
 * operator that fits its kind, and the value or two), a switch for deleted
 * records, and a way to clear it all. Rows are combined with AND; a row that is
 * not complete yet is simply not applied. Everything is controlled by the page.
 */
export default function FilterBar({
  fields,
  conditions,
  onConditionsChange,
  search,
  onSearchChange,
  includeDeleted,
  onIncludeDeletedChange,
  onClear,
  dirty,
}: {
  fields: FieldInfo[]
  conditions: ConditionDraft[]
  onConditionsChange: (conditions: ConditionDraft[]) => void
  search: string
  onSearchChange: (search: string) => void
  includeDeleted: boolean
  onIncludeDeletedChange: (value: boolean) => void
  onClear: () => void
  dirty: boolean
}) {
  const { t } = useTranslation('repository')
  const fieldLabel = useFieldLabel()
  const [picking, setPicking] = useState<{ condition: string; which: 'value' | 'value2' } | null>(null)

  function update(id: string, changes: Partial<ConditionDraft>) {
    onConditionsChange(conditions.map((condition) => (condition.id === id ? { ...condition, ...changes } : condition)))
  }

  const pickingCondition = picking ? conditions.find((condition) => condition.id === picking.condition) : undefined
  const pickingField = pickingCondition ? fields.find((field) => field.key === pickingCondition.field) : undefined

  return (
    <section aria-label={t('filters.title')} className="space-y-3 rounded-2xl border repo-border bg-white p-3 dark:bg-slate-900">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t('filters.search')}
          aria-label={t('filters.search')}
          maxLength={200}
          className={`${inputClass} sm:max-w-xs`}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
          <input type="checkbox" className="repo-check" checked={includeDeleted} onChange={(e) => onIncludeDeletedChange(e.target.checked)} />
          {t('filters.includeDeleted')}
        </label>
        <button type="button" onClick={() => onConditionsChange([...conditions, newCondition(fields[0])])} className={secondaryButtonClass}>
          {t('filters.add')}
        </button>
        {dirty && (
          <button type="button" onClick={onClear} className={secondaryButtonClass}>
            {t('filters.clear')}
          </button>
        )}
      </div>

      {conditions.length > 0 && (
        <ul className="space-y-2">
          {conditions.map((condition, index) => {
            const field = fields.find((candidate) => candidate.key === condition.field) ?? fields[0]
            const operators = OPERATORS[field.kind]
            const label = fieldLabel(field)
            return (
              <li key={condition.id} className="flex flex-wrap items-center gap-2">
                <span className="w-8 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">{index === 0 ? '' : t('filters.and')}</span>
                <select
                  value={condition.field}
                  onChange={(e) => {
                    const next = fields.find((candidate) => candidate.key === e.target.value) ?? fields[0]
                    update(condition.id, { field: next.key, op: OPERATORS[next.kind][0], value: '', value2: '', refInfo: undefined })
                  }}
                  aria-label={t('filters.field')}
                  className={`${inputClass} w-44`}
                >
                  {fields.map((candidate) => (
                    <option key={candidate.key} value={candidate.key}>
                      {fieldLabel(candidate)}
                    </option>
                  ))}
                </select>
                <select value={condition.op} onChange={(e) => update(condition.id, { op: e.target.value })} aria-label={t('filters.operator', { field: label })} className={`${inputClass} w-40`}>
                  {operators.map((op) => (
                    <option key={op} value={op}>
                      {t(`filters.ops.${op}`)}
                    </option>
                  ))}
                </select>
                {operatorNeedsValue(condition.op) && (
                  <ValueInput
                    field={field}
                    value={condition.value}
                    onChange={(value) => update(condition.id, { value })}
                    label={t('filters.value', { field: label })}
                    refName={condition.refInfo?.name}
                    onPick={() => setPicking({ condition: condition.id, which: 'value' })}
                  />
                )}
                {operatorNeedsTwoValues(condition.op) && (
                  <>
                    <span className="text-sm text-slate-500 dark:text-slate-400">{t('filters.to')}</span>
                    <ValueInput
                      field={field}
                      value={condition.value2}
                      onChange={(value2) => update(condition.id, { value2 })}
                      label={t('filters.value2', { field: label })}
                      onPick={() => undefined}
                    />
                  </>
                )}
                <button
                  type="button"
                  onClick={() => onConditionsChange(conditions.filter((candidate) => candidate.id !== condition.id))}
                  aria-label={t('filters.remove', { field: label })}
                  className="inline-flex items-center rounded-lg border border-red-300 px-2.5 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                >
                  ✕
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {picking && pickingCondition && pickingField?.tableId && (
        <ReferencePicker
          tableId={pickingField.tableId}
          onClose={() => setPicking(null)}
          onPick={(hit, table) => {
            update(pickingCondition.id, {
              value: hit.id,
              refInfo: { name: hit.name, slug: hit.slug, table_slug: table.slug, table_name: table.name, deleted: false },
            })
            setPicking(null)
          }}
        />
      )}
    </section>
  )
}
