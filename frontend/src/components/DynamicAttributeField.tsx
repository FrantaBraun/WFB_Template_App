/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import type { UserAttribute } from '../config/userAttributes'

interface Props {
  attribute: UserAttribute
  value: unknown
  onChange: (key: string, value: unknown) => void
}

/**
 * Renders one form field for a user-configurable attribute (from
 * config.json, see config/userAttributes.ts), picking the input type
 * (checkbox/number/date/text) based on `attribute.type`.
 */
export default function DynamicAttributeField({ attribute, value, onChange }: Props) {
  const { t } = useTranslation()
  const label = t(attribute.i18nKey)

  if (attribute.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(attribute.key, e.target.checked)}
          className="rounded border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-900"
        />
        {label}
        {attribute.required && <span className="text-red-600 dark:text-red-400">*</span>}
      </label>
    )
  }

  const inputType = attribute.type === 'number' ? 'number' : attribute.type === 'date' ? 'date' : 'text'

  return (
    <div>
      <label htmlFor={`attr-${attribute.key}`} className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
        {label}
        {attribute.required && <span className="text-red-600 dark:text-red-400"> *</span>}
      </label>
      <input
        id={`attr-${attribute.key}`}
        type={inputType}
        value={(value as string | number | undefined) ?? ''}
        onChange={(e) => {
          if (attribute.type === 'number') {
            const num = e.target.valueAsNumber
            onChange(attribute.key, Number.isNaN(num) ? undefined : num)
          } else {
            onChange(attribute.key, e.target.value)
          }
        }}
        className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
      />
    </div>
  )
}
