/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

const OG_LOCALES: Record<string, string> = { cs: 'cs_CZ', en: 'en_US' }

interface ShareDefaults {
  image: string
  card: string
}

let shareDefaults: ShareDefaults | undefined

/**
 * The share image and the card type index.html carries, read once before the
 * first page overwrites them: an application that ships its own (an absolute
 * og:image, summary_large_image) keeps it on every page, the others get the
 * logo as a small card. Link-preview bots never run this hook, so what they
 * show is whatever index.html says; this keeps a client that does run it in
 * agreement with them.
 */
function readShareDefaults(): ShareDefaults {
  if (!shareDefaults) {
    shareDefaults = {
      image: document.head.querySelector<HTMLMetaElement>('meta[property="og:image"]')?.content || `${window.location.origin}/logo.png`,
      card: document.head.querySelector<HTMLMetaElement>('meta[name="twitter:card"]')?.content || 'summary',
    }
  }
  return shareDefaults
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
 * are not meant to show up in search results (sign-in, account, administration).
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
}: { title?: string; description?: string; noindex?: boolean } = {}) {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const language = (i18n.resolvedLanguage ?? i18n.language ?? 'cs').split('-')[0]
  const brand = t('nav.brand')
  const defaultDescription = t('meta.description')

  useEffect(() => {
    const fullTitle = title ? `${title} — ${brand}` : brand
    const text = description || defaultDescription
    const url = `${window.location.origin}${pathname}`

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
    const share = readShareDefaults()
    upsertMeta('property', 'og:image', share.image)
    upsertMeta('name', 'twitter:card', share.card)
    upsertMeta('name', 'twitter:image', share.image)
  }, [title, description, noindex, language, brand, defaultDescription, pathname])
}
