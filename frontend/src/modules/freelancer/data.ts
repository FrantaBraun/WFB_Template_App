/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Small public-data hooks of the freelancer site: what the pages read from
// other modules' public endpoints. Each degrades to "nothing" when the module
// or the backend is not there, so a page never breaks because of a preview.
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../api/client'

/** Fetches `path` (with the active language appended) once per language; `null` while loading or when it fails. */
export function usePublicData<T>(path: string): T | null {
  const { i18n } = useTranslation()
  const language = i18n.resolvedLanguage ?? i18n.language
  const [state, setState] = useState<{ key: string; data: T | null }>({ key: '', data: null })
  const key = `${path}|${language}`

  useEffect(() => {
    let cancelled = false
    const separator = path.includes('?') ? '&' : '?'
    apiFetch(`${path}${separator}language=${encodeURIComponent(language)}`)
      .then((resp) => (resp.ok ? resp.json() : null))
      .catch(() => null)
      .then((data: T | null) => {
        if (!cancelled) setState({ key, data })
      })
    return () => {
      cancelled = true
    }
  }, [path, language, key])

  // data of an earlier language must not be shown for the current one
  return state.key === key ? state.data : null
}

export interface ProjectPreview {
  slug: string
  title: string
  summary: string
  url: string | null
  status: 'live' | 'in_preparation'
  tags: string[]
}

export interface ContactInfo {
  details: { email: string | null; address: string | null; github_url: string | null; linkedin_url: string | null }
}

export interface ProviderInfo {
  name: string
  ico: string
  dic: string
  vat_payer: boolean
  address: string
  registration: string
  email: string
  phone: string
  web: string
  dpo_email: string
  effective_from: string | null
  configured: boolean
}
