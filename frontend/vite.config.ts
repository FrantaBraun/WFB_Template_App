/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Where the boards module serves the sitemap (backend/app/modules/boards/sitemap.py).
const SITEMAP_API_PATH = '/api/modules/boards/sitemap.xml'

// Pages that are not for search engines: signing in, the account, the
// payments and the administration, the diagnostics, and the JSON API.
// (Their pages also ask not to be indexed - usePageMeta's `noindex` - for
// crawlers that read a page anyway.)
const ROBOTS_DISALLOW = [
  '/api/',
  '/login',
  '/register',
  '/account',
  '/oauth/',
  '/consent',
  '/my-posts',
  '/my-payments',
  '/receipts',
  '/moderation',
  '/categories/new',
  '/platba/',
  '/version',
  '/release-news',
]

/**
 * robots.txt, written from the build's VITE_APP_URL instead of kept as a
 * static file: its `Sitemap:` line has to be an absolute address, which is
 * the one thing a file in public/ cannot know. (Without VITE_APP_URL the line
 * is left out.) Served by the dev server as well.
 */
function robotsTxt(appUrl: string): Plugin {
  const body = () =>
    [
      'User-agent: *',
      'Allow: /',
      ...ROBOTS_DISALLOW.map((path) => `Disallow: ${path}`),
      ...(appUrl ? ['', `Sitemap: ${appUrl.replace(/\/+$/, '')}/sitemap.xml`] : []),
      '',
    ].join('\n')

  return {
    name: 'robots-txt',
    configureServer(server) {
      server.middlewares.use('/robots.txt', (_request, response) => {
        response.setHeader('Content-Type', 'text/plain; charset=utf-8')
        response.end(body())
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: body() })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')

  return {
    // @tailwindcss/vite replaces the old PostCSS pipeline (no tailwind.config.js
    // or postcss.config.js needed) - it scans source files for class names and
    // injects the generated CSS directly, driven entirely by the
    // `@import "tailwindcss"` in src/index.css.
    plugins: [react(), tailwindcss(), robotsTxt(env.VITE_APP_URL ?? '')],
    server: {
      // In production the web server maps /sitemap.xml to the backend
      // (scripts/install.sh); the dev server does the same, so the sitemap
      // can be looked at locally.
      proxy: {
        '/sitemap.xml': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: () => SITEMAP_API_PATH,
        },
      },
    },
  }
})
