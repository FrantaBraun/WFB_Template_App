/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { Plugin } from 'vite'

/**
 * The pages a search engine may index, in the order the sitemap lists them.
 * HomeRepository is an application behind a sign-in: the home page is the only
 * public page with content, everything else (sign-in, account, the repositories)
 * is noindex.
 */
export const SITEMAP_PATHS = ['/']

/** The share image in public/, drawn from design/og-image.html (see CLAUDE.md). */
const SHARE_IMAGE = '/og-image.png'

/**
 * Writes robots.txt and sitemap.xml into the build and adds the tags to
 * index.html that need the site's absolute public address, which the build
 * knows as VITE_APP_URL: the share image, its Twitter twin and og:url. Without
 * it the sitemap is left out (a sitemap with wrong or relative addresses is
 * worse than none) and the build says so.
 *
 * robots.txt allows everything on purpose: pages that must stay out of search
 * results say so with a noindex meta tag, which a crawler can only read if
 * robots.txt lets it fetch the page, and a Disallow list would also announce
 * where the private areas live.
 */
export function seoFiles(siteUrl: string | undefined): Plugin {
  const base = siteUrl?.trim().replace(/\/+$/, '')

  return {
    name: 'seo-files',
    transformIndexHtml() {
      if (!base) return []
      return [
        { tag: 'meta', attrs: { property: 'og:url', content: `${base}/` }, injectTo: 'head' as const },
        { tag: 'meta', attrs: { property: 'og:image', content: `${base}${SHARE_IMAGE}` }, injectTo: 'head' as const },
        { tag: 'meta', attrs: { name: 'twitter:image', content: `${base}${SHARE_IMAGE}` }, injectTo: 'head' as const },
      ]
    },
    generateBundle() {
      const robots = ['User-agent: *', 'Allow: /', ...(base ? ['', `Sitemap: ${base}/sitemap.xml`] : [])].join('\n') + '\n'
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots })

      if (!base) {
        this.warn("VITE_APP_URL is not set: no sitemap.xml was written and index.html has no og:url / og:image. Set it to the site's public address.")
        return
      }
      const urls = SITEMAP_PATHS.map((path) => `  <url><loc>${base}${path}</loc></url>`).join('\n')
      const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap })
    },
  }
}
