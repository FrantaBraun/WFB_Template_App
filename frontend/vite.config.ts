/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { seoFiles } from './vite-plugins/seo'

export default defineConfig(({ mode }) => ({
  // @tailwindcss/vite replaces the old PostCSS pipeline (no tailwind.config.js
  // or postcss.config.js needed) - it scans source files for class names and
  // injects the generated CSS directly, driven entirely by the
  // `@import "tailwindcss"` in src/index.css.
  // seoFiles writes robots.txt / sitemap.xml and the og:image tag from VITE_APP_URL.
  plugins: [react(), tailwindcss(), seoFiles(loadEnv(mode, '.', 'VITE_').VITE_APP_URL)],
}))
