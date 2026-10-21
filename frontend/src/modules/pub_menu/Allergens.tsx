/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { ALLERGENS } from './api'
import { mutedClass } from './ui'

/** The allergens of a dish as "Alergeny: 1, 3, 7" - each number's name is its tooltip. */
export function AllergenList({ numbers }: { numbers: number[] }) {
  const { t } = useTranslation('pub_menu')
  if (numbers.length === 0) return null
  return (
    <span className={mutedClass}>
      {t('allergens.label')}:{' '}
      {numbers.map((number, index) => (
        <span key={number}>
          {index > 0 && ', '}
          <abbr title={t(`allergens.names.${number}`)} className="cursor-help no-underline">
            {number}
          </abbr>
        </span>
      ))}
    </span>
  )
}

/** The 14 allergens with their numbers, to read the numbers on the menu by. */
export function AllergenLegend() {
  const { t } = useTranslation('pub_menu')
  return (
    <details className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800">
      <summary className="cursor-pointer font-medium">{t('allergens.legendTitle')}</summary>
      <ol className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {ALLERGENS.map((number) => (
          <li key={number}>
            <span className="font-medium">{number}</span> – {t(`allergens.names.${number}`)}
          </li>
        ))}
      </ol>
    </details>
  )
}

interface PickerProps {
  value: number[]
  onChange: (value: number[]) => void
  idPrefix: string
}

/** Toggles for the 14 allergens; the numbers are what a dish stores. */
export function AllergenPicker({ value, onChange, idPrefix }: PickerProps) {
  const { t } = useTranslation('pub_menu')
  return (
    <fieldset>
      <legend className="mb-1 text-sm text-slate-600 dark:text-slate-400">{t('allergens.label')}</legend>
      <div className="flex flex-wrap gap-1.5">
        {ALLERGENS.map((number) => {
          const on = value.includes(number)
          return (
            <button
              key={number}
              id={`${idPrefix}-allergen-${number}`}
              type="button"
              aria-pressed={on}
              title={t(`allergens.names.${number}`)}
              aria-label={`${number} – ${t(`allergens.names.${number}`)}`}
              onClick={() => onChange(on ? value.filter((entry) => entry !== number) : [...value, number].sort((a, b) => a - b))}
              className={`h-8 w-8 rounded-lg border text-sm ${
                on
                  ? 'border-slate-900 bg-slate-900 text-slate-100 dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : 'border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
              }`}
            >
              {number}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
