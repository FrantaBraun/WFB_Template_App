/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Provider details for the legal pages (About, Terms, Privacy, Cookies),
// read at runtime from public/legal.json - static, like config.json and
// modules.json, so each deployment fills in its own provider without a
// rebuild. Field meanings and what the law requires are in the module's
// README (backend/app/modules/stripe_payment_gate/README.md).
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
  effectiveFrom: string
  /** Show the GDPR-specific privacy sections (legal bases, rights, supervisory authority, transfers). */
  gdpr: boolean
  /** App-specific technical cookies/storage entries, listed after the built-in ones on the Cookies page. */
  extraStorage: StorageItem[]
  /**
   * App-specific values for `{{placeholders}}` in the legal texts - e.g. the
   * numbers an application's own rules quote (limits, thresholds, periods).
   * They are exposed under their own names next to the built-in ones, which
   * win on a clash, and are always plain strings in the texts.
   */
  params: Record<string, string | number>
}

const EMPTY: LegalConfig = {
  provider: { name: '', ico: '', dic: '', vatPayer: false, address: '', registration: '', email: '', phone: '', web: '' },
  service: '',
  dpoEmail: '',
  effectiveFrom: '',
  gdpr: true,
  extraStorage: [],
  params: {},
}

let configPromise: Promise<LegalConfig> | null = null

async function loadLegalConfig(): Promise<LegalConfig> {
  try {
    const resp = await fetch('/legal.json')
    if (!resp.ok) return EMPTY
    const data = await resp.json()
    return { ...EMPTY, ...data, provider: { ...EMPTY.provider, ...data.provider }, params: { ...data.params } }
  } catch {
    return EMPTY
  }
}

/** Fetches public/legal.json once (cached); null until loaded. */
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
  const { name, ico, address, email } = config.provider
  return Boolean(name && ico && address && email)
}

/** Interpolation values shared by every legal text (see the locales' {{placeholders}}). */
export function legalVars(config: LegalConfig, lang: string, t: (key: string) => string): Record<string, string> {
  const dash = '—'
  const { provider } = config
  return {
    ...Object.fromEntries(Object.entries(config.params).map(([key, value]) => [key, String(value)])),
    name: provider.name || dash,
    ico: provider.ico || dash,
    dic: provider.dic || dash,
    address: provider.address || dash,
    registration: localized(provider.registration, lang) || dash,
    email: provider.email || dash,
    phone: provider.phone || dash,
    web: provider.web || window.location.origin,
    service: localized(config.service, lang) || dash,
    vatStatement: provider.vatPayer
      ? t('stripe_payment_gate:legal.vatPayer')
      : t('stripe_payment_gate:legal.notVatPayer'),
    effectiveFrom: config.effectiveFrom
      ? new Date(config.effectiveFrom).toLocaleDateString(lang)
      : dash,
  }
}
