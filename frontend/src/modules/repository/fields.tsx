/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { MAX_ELEMENTS, MAX_TEXT_LENGTH, elementTypeOf, newId, type Attribute, type ElementType, type RefInfo } from './api'
import type { DraftValue, Entry } from './recordForm'
import { ImageInput } from './images'
import { ReferenceInput } from './references'
import { errorTextClass, hintClass, inputClass, labelClass, secondaryButtonClass } from './ui'

/** What the inputs share: what is known about the records references point at, and a way to add to it. */
export interface FieldContext {
  refs: Record<string, RefInfo>
  rememberRef: (id: string, info: RefInfo) => void
}

function useErrorText() {
  const { t } = useTranslation('repository')
  return (code: string) => t(`record.errors.${code}`, { defaultValue: t('record.errors.generic') })
}

/** The input of one simple value (a whole attribute of a simple type, or one element of a list or map). */
function SimpleInput({
  id,
  type,
  tableId,
  value,
  onChange,
  context,
  label,
  compact,
  invalid,
}: {
  id: string
  type: ElementType
  tableId: string | undefined
  value: string
  onChange: (value: string) => void
  context: FieldContext
  label: string
  compact: boolean
  invalid: boolean
}) {
  const { t } = useTranslation('repository')
  switch (type) {
    case 'text':
      return compact ? (
        <input id={id} value={value} onChange={(e) => onChange(e.target.value)} maxLength={MAX_TEXT_LENGTH} aria-label={label} aria-invalid={invalid} className={inputClass} />
      ) : (
        <textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} maxLength={MAX_TEXT_LENGTH} rows={3} aria-invalid={invalid} className={inputClass} />
      )
    case 'number':
      return <input id={id} type="number" step="any" inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} aria-label={compact ? label : undefined} aria-invalid={invalid} className={inputClass} />
    case 'boolean':
      return (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-label={compact ? label : undefined} aria-invalid={invalid} className={inputClass}>
          <option value="">{t('record.boolean.unset')}</option>
          <option value="true">{t('record.boolean.yes')}</option>
          <option value="false">{t('record.boolean.no')}</option>
        </select>
      )
    case 'date':
      return <input id={id} type="date" value={value} onChange={(e) => onChange(e.target.value)} aria-label={compact ? label : undefined} aria-invalid={invalid} className={inputClass} />
    case 'datetime':
      return <input id={id} type="datetime-local" value={value} onChange={(e) => onChange(e.target.value)} aria-label={compact ? label : undefined} aria-invalid={invalid} className={inputClass} />
    case 'image':
      return <ImageInput value={value} onChange={onChange} label={label} />
    case 'reference':
      return (
        <ReferenceInput
          tableId={tableId ?? ''}
          value={value}
          info={context.refs[value]}
          label={label}
          onChange={(picked, info) => {
            if (info) context.rememberRef(picked, info)
            onChange(picked)
          }}
        />
      )
  }
}

/**
 * The form control(s) of one attribute, by its type: a text area, a number
 * field, a yes/no/not-set choice, a date or date-and-time picker, the image
 * input, the reference picker - and for a list or map an indented row per
 * element (a map also asks for its key) that behaves like the single value of
 * the element type, with buttons to reorder (a list), remove and add. `errors`
 * is the whole {attribute id or "<id>.<element>": code} map of the form.
 */
export default function AttributeField({
  attribute,
  draft,
  onChange,
  context,
  errors,
}: {
  attribute: Attribute
  draft: DraftValue
  onChange: (draft: DraftValue) => void
  context: FieldContext
  errors: Record<string, string>
}) {
  const { t } = useTranslation('repository')
  const errorText = useErrorText()
  const baseId = useId()
  const type = elementTypeOf(attribute)
  const tableId = attribute.config.table_id
  const own = errors[attribute.id]

  const heading = (
    <label htmlFor={`${baseId}-value`} className={labelClass}>
      {attribute.name}
      {attribute.required && <span className="text-red-600 dark:text-red-400" aria-hidden="true"> *</span>}
      {attribute.required && <span className="sr-only"> ({t('record.required')})</span>}
    </label>
  )
  const description = attribute.description && <p className={`${hintClass} mb-1`}>{attribute.description}</p>

  if (attribute.type !== 'list' && attribute.type !== 'map') {
    return (
      <div>
        {type === 'image' || type === 'reference' ? <span className={labelClass}>{attribute.name}{attribute.required && <span className="text-red-600 dark:text-red-400"> *</span>}</span> : heading}
        {description}
        <SimpleInput
          id={`${baseId}-value`}
          type={type}
          tableId={tableId}
          value={draft as string}
          onChange={onChange}
          context={context}
          label={attribute.name}
          compact={false}
          invalid={own !== undefined}
        />
        {own && <p className={errorTextClass}>{errorText(own)}</p>}
      </div>
    )
  }

  const entries = draft as Entry[]
  const isList = attribute.type === 'list'

  function updateEntry(index: number, changes: Partial<Entry>) {
    onChange(entries.map((entry, i) => (i === index ? { ...entry, ...changes } : entry)))
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= entries.length) return
    const next = [...entries]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <fieldset>
      <legend className={labelClass}>
        {attribute.name}
        {attribute.required && <span className="text-red-600 dark:text-red-400"> *</span>}
        <span className="ms-2 text-xs font-normal text-slate-500 dark:text-slate-400">{t(isList ? 'record.listOf' : 'record.mapOf', { type: t(`attributes.types.${type}`) })}</span>
      </legend>
      {description}
      <ol className="space-y-2 border-s-2 repo-border ps-3">
        {entries.map((entry, index) => {
          const entryError = errors[`${attribute.id}.${isList ? index : entry.key}`]
          const entryLabel = isList ? t('record.elementNumber', { name: attribute.name, number: index + 1 }) : t('record.elementKey', { name: attribute.name, key: entry.key || index + 1 })
          return (
            <li key={entry.id} className="space-y-1">
              <div className="flex flex-wrap items-start gap-2">
                {!isList && (
                  <input
                    value={entry.key}
                    onChange={(e) => updateEntry(index, { key: e.target.value })}
                    maxLength={100}
                    placeholder={t('record.keyPlaceholder')}
                    aria-label={t('record.keyOf', { name: attribute.name, number: index + 1 })}
                    aria-invalid={entryError !== undefined}
                    className={`${inputClass} w-40 shrink-0`}
                  />
                )}
                <div className="min-w-0 flex-1 basis-48">
                  <SimpleInput
                    id={`${baseId}-${entry.id}`}
                    type={type}
                    tableId={tableId}
                    value={entry.value}
                    onChange={(value) => updateEntry(index, { value })}
                    context={context}
                    label={entryLabel}
                    compact
                    invalid={entryError !== undefined}
                  />
                </div>
                <div className="flex shrink-0 gap-1">
                  {isList && (
                    <>
                      <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={t('record.moveUp', { label: entryLabel })} className={secondaryButtonClass}>
                        ↑
                      </button>
                      <button type="button" onClick={() => move(index, 1)} disabled={index === entries.length - 1} aria-label={t('record.moveDown', { label: entryLabel })} className={secondaryButtonClass}>
                        ↓
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    onClick={() => onChange(entries.filter((_, i) => i !== index))}
                    aria-label={t('record.removeElement', { label: entryLabel })}
                    className="inline-flex items-center rounded-lg border border-red-300 px-2.5 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                  >
                    ✕
                  </button>
                </div>
              </div>
              {entryError && <p className={errorTextClass}>{errorText(entryError)}</p>}
            </li>
          )
        })}
      </ol>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onChange([...entries, { id: newId(), key: '', value: '' }])}
          disabled={entries.length >= MAX_ELEMENTS}
          className={secondaryButtonClass}
        >
          {t(isList ? 'record.addElement' : 'record.addEntry')}
        </button>
        <span className={hintClass}>{t('record.elementCount', { count: entries.length, max: MAX_ELEMENTS })}</span>
      </div>
      {own && <p className={errorTextClass}>{errorText(own)}</p>}
    </fieldset>
  )
}
