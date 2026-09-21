/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import DOMPurify from 'dompurify'
import { marked } from 'marked'

export const KB_CONTENT_CLASS =
  'space-y-2 text-sm text-slate-700 dark:text-slate-300 [&_a]:underline [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:py-0.5 dark:[&_code]:bg-slate-800 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-100 [&_pre]:p-3 dark:[&_pre]:bg-slate-800 [&_ul]:list-disc [&_ul]:pl-5'

/**
 * KB page content -> sanitized HTML for rendering, per content_format -
 * "markdown" is parsed with marked() first, "html" is already HTML and skips
 * that step, but either way the result always goes through
 * DOMPurify.sanitize() before reaching dangerouslySetInnerHTML: a public
 * collection's or integration's KB reaches fully anonymous visitors
 * regardless of which format a given page happens to be in (CLAUDE.md's
 * "freeform text is never rendered as raw HTML" rule). { async: false } pins
 * marked's overload to a plain string return (no extensions register async
 * behavior here) rather than the string | Promise<string> union its default
 * overload would otherwise produce.
 */
export function renderKbContent(content: string, contentFormat: string): string {
  const html = contentFormat === 'html' ? content : marked(content, { async: false })
  return DOMPurify.sanitize(html)
}
