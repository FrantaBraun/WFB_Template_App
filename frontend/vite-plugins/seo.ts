/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { Plugin } from 'vite'

/** The public pages, in the order the sitemap lists them (detail pages such as /portfolio/<slug> are reached by links from these). */
export const SITEMAP_PATHS = ['/', '/services', '/portfolio', '/pricing', '/about', '/contact', '/privacy', '/terms', '/cookies']

/**
 * Writes robots.txt and sitemap.xml into the build and adds the share-image tag
 * to index.html - the things that need the site's absolute public address,
 * which the build knows as VITE_APP_URL. Without it the sitemap is left out
 * (a sitemap with wrong or relative addresses is worse than none) and the build
 * says so.
 *
 * robots.txt allows everything on purpose: pages that must stay out of search
 * results (sign-in, account, administration) say so with a noindex meta tag,
 * which a crawler can only read if robots.txt lets it fetch the page, and a
 * Disallow list would also announce where the administration lives.
 */
export function seoFiles(siteUrl: string | undefined): Plugin {
  const base = siteUrl?.trim().replace(/\/+$/, '')

  return {
    name: 'seo-files',
    transformIndexHtml() {
      if (!base) return []
      return [{ tag: 'meta', attrs: { property: 'og:image', content: `${base}/logo.png` }, injectTo: 'head' as const }]
    },
    generateBundle() {
      const robots = ['User-agent: *', 'Allow: /', ...(base ? ['', `Sitemap: ${base}/sitemap.xml`] : [])].join('\n') + '\n'
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots })

      if (!base) {
        this.warn('VITE_APP_URL is not set: no sitemap.xml was written and index.html has no og:image. Set it to the site\'s public address.')
        return
      }
      const urls = SITEMAP_PATHS.map((path) => `  <url><loc>${base}${path === '/' ? '/' : path}</loc></url>`).join('\n')
      const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap })
    },
  }
}
