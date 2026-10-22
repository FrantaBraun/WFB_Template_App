/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { elementTypeOf, formatDate, formatNumber, listValues, mapEntries, type Attribute, type ElementType, type RefInfo, type StoredValue } from './api'
import { RecordImage } from './images'
import { RefLink } from './references'

export type ViewVariant = 'cell' | 'full'

const CELL_LIST_LIMIT = 3
const CELL_MAP_LIMIT = 2

function Empty() {
  return <span className="text-slate-400 dark:text-slate-500">—</span>
}

function Simple({ type, value, refs, variant, label }: { type: ElementType; value: StoredValue; refs: Record<string, RefInfo>; variant: ViewVariant; label: string }) {
  const { t, i18n } = useTranslation('repository')
  const language = i18n.resolvedLanguage ?? 'cs'
  switch (type) {
    case 'text':
      return <span className={variant === 'full' ? 'whitespace-pre-wrap break-words' : 'line-clamp-2 break-words'}>{String(value)}</span>
    case 'number':
      return <span className="tabular-nums">{formatNumber(Number(value), language)}</span>
    case 'boolean':
      return <span>{value === true ? t('record.boolean.yes') : t('record.boolean.no')}</span>
    case 'date':
    case 'datetime':
      return <span>{formatDate(String(value), language)}</span>
    case 'image':
      return (
        <RecordImage
          id={String(value)}
          alt={label}
          className={variant === 'cell' ? 'h-10 w-10 rounded object-cover' : 'max-h-80 max-w-full rounded-lg border border-slate-200 object-contain dark:border-slate-700'}
        />
      )
    case 'reference':
      return <RefLink info={refs[String(value)]} />
  }
}

/**
 * A stored value as it is shown: in a table cell or grid card (`cell`: short -
 * text is cut to two lines, a list shows its first elements and "+n") or on
 * the record's own page (`full`: everything, a list as a list and a map as
 * key / value pairs). A value that is not set is a dash.
 */
export default function ValueView({ attribute, value, refs, variant }: { attribute: Attribute; value: StoredValue; refs: Record<string, RefInfo>; variant: ViewVariant }) {
  const { t } = useTranslation('repository')
  const type = elementTypeOf(attribute)
  if (value === undefined || value === null) return <Empty />

  if (attribute.type === 'list') {
    const elements = listValues(value)
    if (elements.length === 0) return <Empty />
    if (variant === 'full') {
      return (
        <ol className="list-decimal space-y-1 ps-5">
          {elements.map((element, index) => (
            <li key={index}>
              <Simple type={type} value={element} refs={refs} variant="full" label={attribute.name} />
            </li>
          ))}
        </ol>
      )
    }
    const shown = elements.slice(0, CELL_LIST_LIMIT)
    return (
      <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
        {shown.map((element, index) => (
          <span key={index} className="max-w-[12rem]">
            <Simple type={type} value={element} refs={refs} variant="cell" label={attribute.name} />
          </span>
        ))}
        {elements.length > shown.length && <span className="text-slate-500 dark:text-slate-400">{t('record.more', { count: elements.length - shown.length })}</span>}
      </span>
    )
  }

  if (attribute.type === 'map') {
    const entries = mapEntries(value)
    if (entries.length === 0) return <Empty />
    if (variant === 'full') {
      return (
        <dl className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-1">
          {entries.map(([key, element]) => (
            <div key={key} className="contents">
              <dt className="font-medium text-slate-600 dark:text-slate-400">{key}</dt>
              <dd>
                <Simple type={type} value={element} refs={refs} variant="full" label={`${attribute.name}: ${key}`} />
              </dd>
            </div>
          ))}
        </dl>
      )
    }
    const shown = entries.slice(0, CELL_MAP_LIMIT)
    return (
      <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
        {shown.map(([key, element]) => (
          <span key={key} className="max-w-[14rem]">
            <span className="text-slate-500 dark:text-slate-400">{key}: </span>
            <Simple type={type} value={element} refs={refs} variant="cell" label={`${attribute.name}: ${key}`} />
          </span>
        ))}
        {entries.length > shown.length && <span className="text-slate-500 dark:text-slate-400">{t('record.more', { count: entries.length - shown.length })}</span>}
      </span>
    )
  }

  return <Simple type={type} value={value} refs={refs} variant={variant} label={attribute.name} />
}
