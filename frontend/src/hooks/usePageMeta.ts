/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

const OG_LOCALES: Record<string, string> = { cs: 'cs_CZ', en: 'en_US' }
const JSON_LD_ID = 'page-json-ld'
/** Search results show about this much of a description; the rest is cut off. */
const DESCRIPTION_MAX = 160

/** The address of a path on this site, as search engines and link previews want it (absolute). */
export function absoluteUrl(path: string): string {
  return `${window.location.origin}${path}`
}

/**
 * A description as a search result shows it: one line of at most `max`
 * characters, cut at a word (not in the middle of one) with an ellipsis. Text
 * that already fits is only tidied (whitespace and line breaks collapsed).
 */
export function clipDescription(text: string, max = DESCRIPTION_MAX): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  if (flat.length <= max) return flat
  const cut = flat.slice(0, max - 1)
  const lastSpace = cut.lastIndexOf(' ')
  const words = lastSpace > max / 2 ? cut.slice(0, lastSpace) : cut
  return `${words.replace(/[\s.,;:!?\-–—]+$/, '')}…`
}

function upsertMeta(attribute: 'name' | 'property', key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`)
  if (!element) {
    element = document.createElement('meta')
    element.setAttribute(attribute, key)
    document.head.appendChild(element)
  }
  element.content = content
}

/** Writes the page's structured data (one JSON-LD script, reused), or removes it when there is none. */
function setJsonLd(json: string) {
  let element = document.getElementById(JSON_LD_ID)
  if (!json) {
    element?.remove()
    return
  }
  if (!element) {
    element = document.createElement('script')
    element.id = JSON_LD_ID
    element.setAttribute('type', 'application/ld+json')
    document.head.appendChild(element)
  }
  element.textContent = json
}

function upsertLink(rel: string, href: string) {
  let element = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`)
  if (!element) {
    element = document.createElement('link')
    element.rel = rel
    document.head.appendChild(element)
  }
  element.href = href
}

/**
 * Sets what a page tells search engines and link previews: the document
 * title (suffixed with the application's name, `nav.brand`), the description
 * (the page's own, else the application's `meta.description`), a canonical
 * URL, Open Graph / Twitter card tags, the robots directive and `<html lang>`.
 * Every application sets its own `nav.brand` and `meta.description` in its
 * locale files, so nothing here names one. Pass `noindex` for pages that
 * are not meant to show up in search results (sign-in, account, administration,
 * a page that does not exist). `jsonLd` is the page's structured data
 * (schema.org, an object or a list of them), written as one JSON-LD script.
 * A description is tidied and cut to what a search result shows
 * (clipDescription).
 *
 * Meta elements are created once and reused (queried by selector) rather
 * than duplicated on every navigation. They are written client-side, so
 * crawlers that run JavaScript (Google) see the per-page values, while ones
 * that do not (most link-preview bots) only see what index.html carries.
 */
export default function usePageMeta({
  title,
  description,
  noindex = false,
  jsonLd,
}: {
  title?: string
  description?: string
  noindex?: boolean
  jsonLd?: Record<string, unknown> | Record<string, unknown>[]
} = {}) {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const language = (i18n.resolvedLanguage ?? i18n.language ?? 'cs').split('-')[0]
  const brand = t('nav.brand')
  const defaultDescription = t('meta.description')
  // A string, so the effect below runs when the data changes, not when a new object with the same data is built.
  const jsonLdText = jsonLd ? JSON.stringify(jsonLd) : ''

  useEffect(() => {
    const fullTitle = title ? `${title} — ${brand}` : brand
    const text = clipDescription(description || defaultDescription)
    const url = absoluteUrl(pathname)

    document.documentElement.lang = language
    document.title = fullTitle
    upsertMeta('name', 'description', text)
    upsertMeta('name', 'robots', noindex ? 'noindex, nofollow' : 'index, follow')
    upsertLink('canonical', url)

    upsertMeta('property', 'og:type', 'website')
    upsertMeta('property', 'og:site_name', brand)
    upsertMeta('property', 'og:title', fullTitle)
    upsertMeta('property', 'og:description', text)
    upsertMeta('property', 'og:url', url)
    upsertMeta('property', 'og:locale', OG_LOCALES[language] ?? language)
    upsertMeta('property', 'og:image', absoluteUrl('/logo.png'))
    upsertMeta('property', 'og:image:alt', brand)
    upsertMeta('name', 'twitter:card', 'summary')
    upsertMeta('name', 'twitter:title', fullTitle)
    upsertMeta('name', 'twitter:description', text)
    upsertMeta('name', 'twitter:image', absoluteUrl('/logo.png'))
    setJsonLd(jsonLdText)
  }, [title, description, noindex, language, brand, defaultDescription, pathname, jsonLdText])
}
