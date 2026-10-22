/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../api/client'
import {
  API_BASE,
  ApiError,
  MAX_IMAGE_BYTES,
  MAX_IMAGE_SIDE,
  fetchJson,
  fieldErrors,
  limitReached,
  sendJson,
  type ImageInfo,
} from './api'
import { errorTextClass, hintClass, inputClass, secondaryButtonClass } from './ui'

// Images are private, so an <img src> cannot fetch them (it cannot send the
// bearer token). They are fetched with it and shown from a blob URL; the URL is
// shared by everything on the page that shows the same image and is revoked
// when the last of them goes away.

interface Entry {
  url: Promise<string>
  users: number
}

const cache = new Map<string, Entry>()

/** The blob URL of an image (null while it loads, `failed` when it could not be fetched). */
export function useImageUrl(id: string | null): { url: string | null; failed: boolean } {
  const [state, setState] = useState<{ url: string | null; failed: boolean }>({ url: null, failed: false })

  useEffect(() => {
    if (!id) {
      setState({ url: null, failed: false })
      return
    }
    let cancelled = false
    let entry = cache.get(id)
    if (!entry) {
      entry = {
        users: 0,
        url: apiFetch(`${API_BASE}/images/${id}`).then(async (resp) => {
          if (!resp.ok) throw new ApiError(resp.status, null)
          return URL.createObjectURL(await resp.blob())
        }),
      }
      cache.set(id, entry)
    }
    const mine = entry
    mine.users += 1
    setState({ url: null, failed: false })
    mine.url.then(
      (url) => !cancelled && setState({ url, failed: false }),
      () => !cancelled && setState({ url: null, failed: true }),
    )
    return () => {
      cancelled = true
      mine.users -= 1
      if (mine.users === 0) {
        if (cache.get(id) === mine) cache.delete(id)
        mine.url.then(
          (url) => URL.revokeObjectURL(url),
          () => undefined,
        )
      }
    }
  }, [id])

  return state
}

/** An image of a record, loaded through the API. */
export function RecordImage({ id, alt, className }: { id: string; alt: string; className?: string }) {
  const { t } = useTranslation('repository')
  const { url, failed } = useImageUrl(id)
  if (failed) {
    return (
      <span className={`${className ?? ''} inline-flex items-center justify-center bg-slate-200 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400`}>
        {t('image.unavailable')}
      </span>
    )
  }
  if (!url) return <span className={`${className ?? ''} inline-block animate-pulse bg-slate-200 dark:bg-slate-800`} aria-hidden="true" />
  return <img src={url} alt={alt} loading="lazy" className={className} />
}

/**
 * What is uploaded for a picked file: left alone when it is a GIF (a canvas
 * would flatten the animation) or already small enough in size and pixels,
 * otherwise scaled down to MAX_IMAGE_SIDE and re-encoded (png and webp stay
 * what they are, anything else becomes jpeg). The server checks it all again.
 */
export async function prepareImage(file: File): Promise<Blob> {
  if (file.type === 'image/gif') return file
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    return file // not something the browser can draw: the server will say what is wrong with it
  }
  const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(bitmap.width, bitmap.height))
  if (scale === 1 && file.size <= MAX_IMAGE_BYTES) {
    bitmap.close()
    return file
  }
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(bitmap.width * scale))
  canvas.height = Math.max(1, Math.round(bitmap.height * scale))
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  const type = file.type === 'image/png' || file.type === 'image/webp' ? file.type : 'image/jpeg'
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, 0.88))
  return blob && (scale < 1 || blob.size < file.size) ? blob : file
}

/** The translated text of a failed upload or import. */
function useImageErrorText() {
  const { t } = useTranslation('repository')
  return (error: unknown): string => {
    const limit = limitReached(error)
    if (limit) return t('image.errors.quota')
    const errors = fieldErrors(error)
    const code = errors.file ?? errors.url
    return t(`image.errors.${code ?? 'generic'}`, { defaultValue: t('image.errors.generic') })
  }
}

/**
 * Picks an image for an attribute: shows the current one and lets the user
 * upload a file (scaled down first, see prepareImage), import one from an
 * address (the server downloads it) or remove it. `value` is the image's id,
 * '' when there is none.
 */
export function ImageInput({ value, onChange, label }: { value: string; onChange: (id: string) => void; label: string }) {
  const { t } = useTranslation('repository')
  const errorText = useImageErrorText()
  const fileInput = useRef<HTMLInputElement>(null)
  const urlId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [address, setAddress] = useState('')

  async function upload(file: File) {
    setBusy(true)
    setError(null)
    try {
      const blob = await prepareImage(file)
      if (blob.size > MAX_IMAGE_BYTES) {
        setError(t('image.errors.too_large'))
        return
      }
      const form = new FormData()
      form.append('file', blob, file.name)
      const image = await fetchJson<ImageInfo>(`${API_BASE}/images`, { method: 'POST', body: form })
      onChange(image.id)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  async function importFromAddress() {
    setBusy(true)
    setError(null)
    try {
      const image = await sendJson<ImageInfo>(`${API_BASE}/images/import-url`, 'POST', { url: address.trim() })
      onChange(image.id)
      setImporting(false)
      setAddress('')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      {value && <RecordImage id={value} alt={label} className="max-h-40 max-w-full rounded-lg border border-slate-200 object-contain dark:border-slate-700" />}
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileInput}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="sr-only"
          aria-label={t('image.chooseFile', { name: label })}
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          tabIndex={-1}
        />
        <button type="button" disabled={busy} onClick={() => fileInput.current?.click()} className={secondaryButtonClass}>
          {busy ? t('image.working') : value ? t('image.replace') : t('image.upload')}
        </button>
        <button type="button" disabled={busy} onClick={() => setImporting((open) => !open)} aria-expanded={importing} className={secondaryButtonClass}>
          {t('image.fromAddress')}
        </button>
        {value && (
          <button type="button" disabled={busy} onClick={() => onChange('')} className={secondaryButtonClass}>
            {t('image.remove')}
          </button>
        )}
      </div>
      {importing && (
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={urlId} className="sr-only">
            {t('image.address')}
          </label>
          <input
            id={urlId}
            type="url"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (address.trim() && !busy) void importFromAddress()
              }
            }}
            placeholder="https://…"
            className={`${inputClass} min-w-0 flex-1`}
          />
          <button type="button" disabled={busy || address.trim() === ''} onClick={importFromAddress} className={secondaryButtonClass}>
            {t('image.import')}
          </button>
        </div>
      )}
      <p className={hintClass}>{t('image.hint')}</p>
      {error && <p className={errorTextClass}>{error}</p>}
    </div>
  )
}
