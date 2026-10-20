/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Node, mergeAttributes } from '@tiptap/core'

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/

/**
 * Maps a pasted YouTube or Vimeo link (watch page, short link, embed, shorts,
 * mobile host) to the one embed URL the editor stores, or null for anything
 * else. The result is exactly what the backend's app/services/sanitize.py
 * allows an iframe to load - keep the two in sync: YouTube goes through the
 * privacy-friendly youtube-nocookie.com host, Vimeo through player.vimeo.com
 * (with the ?h= hash an unlisted video needs).
 */
export function parseVideoUrl(input: string): string | null {
  let url: URL
  try {
    url = new URL(input.trim())
  } catch {
    return null
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return null
  const host = url.hostname.toLowerCase().replace(/^(www|m)\./, '')

  let youtubeId: string | null = null
  if (host === 'youtu.be') {
    youtubeId = url.pathname.slice(1).split('/')[0]
  } else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    if (url.pathname === '/watch') youtubeId = url.searchParams.get('v')
    else youtubeId = url.pathname.match(/^\/(?:embed|shorts|live|v)\/([^/?#]+)/)?.[1] ?? null
  }
  if (youtubeId && YOUTUBE_ID.test(youtubeId)) return `https://www.youtube-nocookie.com/embed/${youtubeId}`

  if (host === 'vimeo.com' || host === 'player.vimeo.com') {
    const match = url.pathname.match(/^\/(?:video\/)?(\d{1,12})(?:\/([A-Za-z0-9]{1,30}))?\/?$/)
    if (!match) return null
    const hash = match[2] ?? url.searchParams.get('h')
    return `https://player.vimeo.com/video/${match[1]}${hash && /^[A-Za-z0-9]{1,30}$/.test(hash) ? `?h=${hash}` : ''}`
  }
  return null
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    videoEmbed: {
      /** Inserts a video block; `src` must come from parseVideoUrl(). */
      setVideo: (options: { src: string }) => ReturnType
    }
  }
}

/**
 * A block-level video, stored as a plain <iframe src="…embed URL…">. It only
 * parses back iframes whose src parseVideoUrl() accepts, so editing HTML
 * source (or pasting) can't smuggle another origin into the editor; the
 * server sanitizer enforces the same rule again on save and adds the
 * sandbox / loading / referrerpolicy attributes.
 */
export const VideoEmbed = Node.create({
  name: 'video',
  group: 'block',
  atom: true,
  draggable: true,

  addAttributes() {
    return { src: { default: null } }
  },

  parseHTML() {
    return [
      {
        tag: 'iframe[src]',
        getAttrs: (element) => {
          const src = parseVideoUrl((element as HTMLElement).getAttribute('src') ?? '')
          return src ? { src } : false
        },
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['iframe', mergeAttributes(HTMLAttributes, { allowfullscreen: 'true', title: 'Video' })]
  },

  addCommands() {
    return {
      setVideo:
        (options) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs: options }),
    }
  },
})
