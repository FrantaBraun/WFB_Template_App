/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fieldErrors, repositoryApi, sendJson, type RepositoryDetail } from './api'
import { COLOR_SCHEMES, SCHEME_SWATCH, schemeClass, type ColorScheme } from './schemes'
import SlugField, { type SlugStatus } from './SlugField'
import { errorTextClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useSaveErrorText } from './ui'

/** The colour schemes as a radio group of swatches - the page around it takes the chosen colours at once. */
function SchemePicker({ value, onChange }: { value: string; onChange: (scheme: ColorScheme) => void }) {
  const { t } = useTranslation('repository')
  return (
    <fieldset>
      <legend className={labelClass}>{t('repository.fields.colorScheme')}</legend>
      <div className="flex flex-wrap gap-2">
        {COLOR_SCHEMES.map((scheme) => (
          <label
            key={scheme}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm ${
              value === scheme
                ? 'border-slate-900 bg-slate-100 dark:border-slate-100 dark:bg-slate-800'
                : 'border-slate-300 bg-white hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800'
            } text-slate-800 dark:text-slate-200`}
          >
            <input type="radio" name="color_scheme" value={scheme} checked={value === scheme} onChange={() => onChange(scheme)} className="sr-only" />
            <span className="inline-block h-4 w-4 rounded-full border border-black/10" style={{ backgroundColor: SCHEME_SWATCH[scheme] }} aria-hidden="true" />
            {t(`scheme.${scheme}`)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/**
 * The form of a repository - name, description, slug, colour scheme - for
 * creating one (no `repository`) and for editing one. It tints itself with
 * the scheme being chosen, so the choice is seen before it is saved.
 */
export default function RepositoryForm({
  repository,
  onSaved,
  onCancel,
}: {
  repository?: RepositoryDetail
  onSaved: (saved: RepositoryDetail) => void
  onCancel: () => void
}) {
  const { t } = useTranslation('repository')
  const saveErrorText = useSaveErrorText()
  const [name, setName] = useState(repository?.name ?? '')
  const [description, setDescription] = useState(repository?.description ?? '')
  const [slug, setSlug] = useState(repository?.slug ?? '')
  const [scheme, setScheme] = useState<string>(repository?.color_scheme ?? COLOR_SCHEMES[0])
  const [slugStatus, setSlugStatus] = useState<SlugStatus>('idle')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [slugError, setSlugError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSlugError(null)
    const body = { name, description, slug: slug || null, color_scheme: scheme }
    try {
      const saved = repository
        ? await sendJson<RepositoryDetail>(repositoryApi(repository.slug), 'PATCH', body)
        : await sendJson<RepositoryDetail>(`${API_BASE}/repositories`, 'POST', body)
      onSaved(saved)
    } catch (err) {
      const errors = fieldErrors(err)
      if (errors.slug) setSlugError(errors.slug)
      else setError(saveErrorText(err, 'repository.form.saveError'))
      setSaving(false)
    }
  }

  const canSave = name.trim() !== '' && slug !== '' && slugStatus !== 'bad' && !saving

  return (
    <form onSubmit={submit} className={`${schemeClass(scheme)} repo-tint-bg space-y-5 rounded-xl p-4`}>
      <div>
        <label htmlFor="repository-name" className={labelClass}>
          {t('repository.fields.name')}
        </label>
        <input id="repository-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required className={inputClass} />
      </div>
      <div>
        <label htmlFor="repository-description" className={labelClass}>
          {t('repository.fields.description')}
        </label>
        <textarea id="repository-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={3} className={inputClass} />
      </div>
      <SlugField
        scope="repository"
        name={name}
        value={slug}
        onChange={setSlug}
        currentSlug={repository?.slug}
        autoFromName={!repository}
        onStatus={setSlugStatus}
        serverError={slugError}
      />
      <SchemePicker value={scheme} onChange={setScheme} />
      {error && <p className={errorTextClass}>{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={!canSave} className={primaryButtonClass}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}
