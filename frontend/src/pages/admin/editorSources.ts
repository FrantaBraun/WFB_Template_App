/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// This app's sources for the shared RichTextEditor (core's
// components/RichTextEditor.tsx takes them as props): @-mention targets
// from /api/admin/mentionable and image uploads to /api/admin/uploads.
import { apiFetch } from '../../api/client'
import type { MentionableItem } from '../../components/RichTextEditor'
import i18n from '../../i18n'

interface AdminMentionable {
  type: 'page' | 'article'
  id: string
  label: string
  slug: string
}

function mentionUrl(item: AdminMentionable): string {
  return item.type === 'page' ? `/${item.slug}` : `/clanek/${item.slug}`
}

export async function loadAdminMentionables(): Promise<MentionableItem[]> {
  const resp = await apiFetch('/api/admin/mentionable')
  if (!resp.ok) return []
  const items: AdminMentionable[] = await resp.json()
  return items.map((item) => ({
    id: `${item.type}-${item.id}`,
    label: item.label,
    url: mentionUrl(item),
    typeLabel: i18n.t(item.type === 'page' ? 'editor.mentionPageType' : 'editor.mentionArticleType'),
  }))
}

export async function uploadAdminImage(file: File): Promise<string> {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await apiFetch('/api/admin/uploads/image', { method: 'POST', body: formData })
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
  const { url } = await resp.json()
  return url
}
