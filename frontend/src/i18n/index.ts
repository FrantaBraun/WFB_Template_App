/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import cs from './locales/cs.json'
import en from './locales/en.json'
import legalCs from './locales/legal.cs.json'
import legalEn from './locales/legal.en.json'

/** Single source of truth for which languages this app ships resources for - also used by Layout.tsx's switcher and applyUserLanguage below. */
export const SUPPORTED_LANGUAGES = ['cs', 'en'] as const

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    // `legal` holds the long texts of the About, Terms and Privacy pages, apart from the
    // rest because they are whole documents; the provider's details are filled in at
    // runtime from public/legal.json (see config/legal.ts).
    resources: {
      cs: { translation: cs, legal: legalCs },
      en: { translation: en, legal: legalEn },
    },
    // cs is the fallback (not the more conventional en) since this template
    // originates from a Czech-first product; supportedLngs pins detection to
    // exactly these two so an unrecognized browser locale falls back cleanly
    // instead of resolving to a partial/missing resource bundle.
    fallbackLng: 'cs',
    supportedLngs: [...SUPPORTED_LANGUAGES],
    // Detection order: a previously-saved choice (localStorage) always wins
    // over the browser's own language (navigator) on repeat visits; caches
    // writes the resolved language back to localStorage so the choice sticks.
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false,
    },
  })

/**
 * Applies the auth service's per-user `language_code` with a fallback
 * cascade: the user's own language if this app ships it, else 'en' if this
 * app ships it, else leave the current language untouched (whatever was
 * active before login - a manual switcher choice or the detector's result).
 * Called after every successful profile load/update so the UI always
 * reflects the signed-in user's preference, not just the browser's.
 */
export function applyUserLanguage(languageCode: string | null | undefined) {
  const supported: readonly string[] = SUPPORTED_LANGUAGES
  if (languageCode && supported.includes(languageCode)) {
    i18n.changeLanguage(languageCode)
  } else if (supported.includes('en')) {
    i18n.changeLanguage('en')
  }
}

export default i18n
