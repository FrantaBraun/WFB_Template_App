/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Provider details for the About, Terms and Privacy pages, read at runtime from
// public/legal.json - static, like config.json and modules.json, so each
// deployment fills in its own provider (who runs the service, how to reach
// them, how long logs are kept) without a rebuild. The same file and shape the
// stripe_payment_gate module's legal pages read; the texts around these values
// are in the `legal` i18n namespace (i18n/locales/legal.{cs,en}.json).
import { useEffect, useState } from 'react'

/** A plain string (same in every language) or one value per language code. */
export type LocalizedText = string | Record<string, string>

export interface StorageItem {
  name: string
  purpose: LocalizedText
  duration: LocalizedText
}

export interface LegalConfig {
  provider: {
    name: string
    ico: string
    dic: string
    vatPayer: boolean
    address: string
    registration: LocalizedText
    email: string
    phone: string
    web: string
  }
  service: LocalizedText
  dpoEmail: string
  /** ISO date from which the texts apply; shown at the top of each page when set. */
  effectiveFrom: string
  /** Show the GDPR-specific privacy sections (legal bases, rights, supervisory authority, transfers). */
  gdpr: boolean
  /** How many days the server keeps its log files (backend LOGGING_DAYS_HISTORY). */
  logRetentionDays: number
  /** App-specific technical cookies/storage entries, listed after the built-in ones on the Privacy page. */
  extraStorage: StorageItem[]
}

const EMPTY: LegalConfig = {
  provider: { name: '', ico: '', dic: '', vatPayer: false, address: '', registration: '', email: '', phone: '', web: '' },
  service: '',
  dpoEmail: '',
  effectiveFrom: '',
  gdpr: true,
  logRetentionDays: 5,
  extraStorage: [],
}

let configPromise: Promise<LegalConfig> | null = null

async function loadLegalConfig(): Promise<LegalConfig> {
  try {
    const resp = await fetch('/legal.json')
    if (!resp.ok) return EMPTY
    const data = await resp.json()
    return { ...EMPTY, ...data, provider: { ...EMPTY.provider, ...data.provider } }
  } catch {
    return EMPTY
  }
}

/** Fetches public/legal.json once (cached); null until loaded. A missing or broken file reads as an empty provider. */
export function useLegalConfig(): LegalConfig | null {
  const [config, setConfig] = useState<LegalConfig | null>(null)
  useEffect(() => {
    let cancelled = false
    configPromise ??= loadLegalConfig()
    configPromise.then((c) => {
      if (!cancelled) setConfig(c)
    })
    return () => {
      cancelled = true
    }
  }, [])
  return config
}

/** Resolves a LocalizedText for `lang`, falling back to cs, en, then any value. */
export function localized(value: LocalizedText, lang: string): string {
  if (typeof value === 'string') return value
  return value[lang] || value.cs || value.en || Object.values(value)[0] || ''
}

/** The minimum a published legal page needs - missing any of these shows a warning banner. */
export function isProviderConfigured(config: LegalConfig): boolean {
  const { name, address, email } = config.provider
  return Boolean(name && address && email)
}

/**
 * Interpolation values shared by every legal text (the `{{placeholders}}` of
 * the `legal` locales). A detail the provider has not filled in reads as a
 * dash, never as an empty gap in a sentence.
 */
export function legalVars(config: LegalConfig, lang: string, brand: { app: string; fullName: string }): Record<string, string> {
  const dash = '—'
  const { provider } = config
  return {
    app: brand.app,
    fullName: brand.fullName,
    name: provider.name || dash,
    ico: provider.ico || dash,
    dic: provider.dic || dash,
    address: provider.address || dash,
    registration: localized(provider.registration, lang) || dash,
    email: provider.email || dash,
    phone: provider.phone || dash,
    web: provider.web || window.location.origin,
    service: localized(config.service, lang) || dash,
    effectiveFrom: config.effectiveFrom ? new Date(config.effectiveFrom).toLocaleDateString(lang) : dash,
    logDays: String(config.logRetentionDays),
  }
}
