/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect } from 'react'

/**
 * Puts one JSON-LD (schema.org) block into <head> while the page is shown, and
 * takes it out again afterwards, so each page describes only itself. Search
 * engines that run JavaScript read it; the content is set as the element's
 * text, never parsed as HTML. Pass null to render nothing (e.g. while the data
 * the block needs is still loading).
 */
export function JsonLd({ id, data }: { id: string; data: Record<string, unknown> | null }) {
  const json = data ? JSON.stringify(data) : null

  useEffect(() => {
    if (!json) return
    const element = document.createElement('script')
    element.type = 'application/ld+json'
    element.id = `jsonld-${id}`
    element.text = json
    document.head.appendChild(element)
    return () => element.remove()
  }, [id, json])

  return null
}
