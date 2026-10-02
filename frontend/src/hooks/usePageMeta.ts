/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect } from 'react'

const SITE = 'ThoughtAuction'

/**
 * Sets the document title (suffixed with the site name), the
 * `<meta name="description">` tag, and matching Open Graph tags
 * (`og:title` / `og:description`) for the current page. Falling back to
 * shared defaults when a page doesn't pass its own title/description keeps
 * every route social-share-ready without each page having to opt in.
 * Meta elements are created once and reused (queried by selector) rather
 * than duplicated on every navigation.
 */
export default function usePageMeta({ title, description }: { title?: string; description?: string } = {}) {
  useEffect(() => {
    document.title = title ? `${title} — ${SITE}` : SITE
    let meta: HTMLMetaElement | null = document.querySelector('meta[name="description"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }
    meta.content = description || 'Publish a thought on a board of your choice. Posts rise with the resonance they earn and sink with age.'

    let ogTitle: HTMLMetaElement | null = document.querySelector('meta[property="og:title"]')
    if (!ogTitle) { ogTitle = document.createElement('meta'); ogTitle.setAttribute('property', 'og:title'); document.head.appendChild(ogTitle) }
    ogTitle.content = document.title

    let ogDesc: HTMLMetaElement | null = document.querySelector('meta[property="og:description"]')
    if (!ogDesc) { ogDesc = document.createElement('meta'); ogDesc.setAttribute('property', 'og:description'); document.head.appendChild(ogDesc) }
    ogDesc.content = meta.content
  }, [title, description])
}
