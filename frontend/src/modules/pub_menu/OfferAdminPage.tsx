/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AllergenPicker } from './Allergens'
import {
  API_BASE,
  errorsOf,
  fetchJson,
  formatPrice,
  parsePrice,
  priceText,
  sendJson,
  statusOf,
  type CategoryAdmin,
  type CategoryKind,
  type ItemAdmin,
} from './api'
import {
  ManageShell,
  Section,
  dangerButtonClass,
  errorClass,
  inputClass,
  labelClass,
  mutedClass,
  okClass,
  primaryButtonClass,
  secondaryButtonClass,
  smallInputClass,
} from './ui'

/**
 * /menu/manage/offer - the standing menu: categories (food or drinks) in the order
 * they are shown, and in each the items with their prices (a beer may have a 0,3 l
 * and a 0,5 l price), allergens and flags - "sold out" shows an item struck through,
 * "hidden" takes it off the public menu without deleting it.
 */
export default function OfferAdminPage() {
  const { t } = useTranslation('pub_menu')
  return (
    <ManageShell title={t('manage.offerTitle')}>
      <Offer />
    </ManageShell>
  )
}

function Offer() {
  const { t } = useTranslation('pub_menu')
  const [categories, setCategories] = useState<CategoryAdmin[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [currency, setCurrency] = useState('CZK')

  useEffect(() => {
    let cancelled = false
    fetchJson<{ currency: string }>(`${API_BASE}/offer`)
      .then((found) => !cancelled && setCurrency(found.currency))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchJson<CategoryAdmin[]>(`${API_BASE}/manage/categories`)
      .then((found) => {
        if (cancelled) return
        setCategories(found)
        setFailed(false)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const reload = () => setReloadKey((key) => key + 1)

  async function moveCategory(index: number, delta: number) {
    if (!categories) return
    const ids = categories.map((category) => category.id)
    const target = index + delta
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    try {
      setCategories(await sendJson<CategoryAdmin[]>(`${API_BASE}/manage/categories/order`, 'POST', { ids }))
    } catch {
      reload()
    }
  }

  if (failed) return <p role="alert" className={errorClass}>{t('manage.loadError')}</p>
  if (!categories) return <p className={mutedClass}>{t('common.loading')}</p>

  return (
    <div className="space-y-6">
      {categories.length === 0 && <p className={mutedClass}>{t('offerAdmin.none')}</p>}
      {categories.map((category, index) => (
        <CategoryEditor
          key={category.id}
          category={category}
          categories={categories}
          currency={currency}
          first={index === 0}
          last={index === categories.length - 1}
          onMove={(delta) => void moveCategory(index, delta)}
          onChanged={reload}
          onReplace={setCategories}
        />
      ))}
      <Section title={t('offerAdmin.addCategory')}>
        <NewCategory onAdded={reload} />
      </Section>
    </div>
  )
}

function NewCategory({ onAdded }: { onAdded: () => void }) {
  const { t } = useTranslation('pub_menu')
  const [name, setName] = useState('')
  const [kind, setKind] = useState<CategoryKind>('food')
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  async function add(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFailed(false)
    try {
      await sendJson<CategoryAdmin>(`${API_BASE}/manage/categories`, 'POST', { name: name.trim(), kind, is_active: true })
      setName('')
      onAdded()
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={add} className="flex flex-wrap items-end gap-3">
      <div className="min-w-48 flex-1">
        <label htmlFor="new-category-name" className={labelClass}>{t('offerAdmin.categoryName')}</label>
        <input id="new-category-name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('offerAdmin.categoryPlaceholder')} className={inputClass} />
      </div>
      <div>
        <label htmlFor="new-category-kind" className={labelClass}>{t('offerAdmin.kind')}</label>
        <select id="new-category-kind" value={kind} onChange={(e) => setKind(e.target.value as CategoryKind)} className={inputClass}>
          <option value="food">{t('offerAdmin.kinds.food')}</option>
          <option value="drink">{t('offerAdmin.kinds.drink')}</option>
        </select>
      </div>
      <button type="submit" disabled={busy} className={secondaryButtonClass}>{busy ? t('common.saving') : t('offerAdmin.addCategoryButton')}</button>
      {failed && <p role="alert" className={`w-full ${errorClass}`}>{t('errors.generic')}</p>}
    </form>
  )
}

interface CategoryProps {
  category: CategoryAdmin
  categories: CategoryAdmin[]
  currency: string
  first: boolean
  last: boolean
  onMove: (delta: number) => void
  onChanged: () => void
  onReplace: (categories: CategoryAdmin[]) => void
}

function CategoryEditor({ category, categories, currency, first, last, onMove, onChanged, onReplace }: CategoryProps) {
  const { t } = useTranslation('pub_menu')
  const [name, setName] = useState(category.name)
  const [description, setDescription] = useState(category.description)
  const [kind, setKind] = useState<CategoryKind>(category.kind)
  const [active, setActive] = useState(category.is_active)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [adding, setAdding] = useState(false)
  const dirty = name !== category.name || description !== category.description || kind !== category.kind || active !== category.is_active

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await sendJson<CategoryAdmin>(`${API_BASE}/manage/categories/${category.id}`, 'PATCH', { name: name.trim(), description: description.trim(), kind, is_active: active })
      setMessage({ kind: 'ok', text: t('common.saved') })
      onChanged()
    } catch {
      setMessage({ kind: 'error', text: t('errors.generic') })
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm(t('offerAdmin.deleteCategoryConfirm', { name: category.name, count: category.items.length }))) return
    setBusy(true)
    try {
      await fetchJson<void>(`${API_BASE}/manage/categories/${category.id}`, { method: 'DELETE' })
      onChanged()
    } catch {
      setMessage({ kind: 'error', text: t('errors.generic') })
      setBusy(false)
    }
  }

  async function moveItem(index: number, delta: number) {
    const ids = category.items.map((item) => item.id)
    const target = index + delta
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    try {
      onReplace(await sendJson<CategoryAdmin[]>(`${API_BASE}/manage/categories/${category.id}/items/order`, 'POST', { ids }))
    } catch {
      onChanged()
    }
  }

  return (
    <Section title={category.name}>
      <form onSubmit={save} className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1">
            <label htmlFor={`category-name-${category.id}`} className={labelClass}>{t('offerAdmin.categoryName')}</label>
            <input id={`category-name-${category.id}`} required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor={`category-kind-${category.id}`} className={labelClass}>{t('offerAdmin.kind')}</label>
            <select id={`category-kind-${category.id}`} value={kind} onChange={(e) => setKind(e.target.value as CategoryKind)} className={inputClass}>
              <option value="food">{t('offerAdmin.kinds.food')}</option>
              <option value="drink">{t('offerAdmin.kinds.drink')}</option>
            </select>
          </div>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('offerAdmin.categoryActive')}
          </label>
          <div className="flex gap-1 pb-0.5">
            <button type="button" onClick={() => onMove(-1)} disabled={first} aria-label={t('offerAdmin.moveCategoryUp')} className={secondaryButtonClass}>↑</button>
            <button type="button" onClick={() => onMove(1)} disabled={last} aria-label={t('offerAdmin.moveCategoryDown')} className={secondaryButtonClass}>↓</button>
          </div>
        </div>
        <div>
          <label htmlFor={`category-description-${category.id}`} className={labelClass}>{t('offerAdmin.categoryDescription')}</label>
          <input id={`category-description-${category.id}`} maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)} className={inputClass} />
        </div>
        {message && <p role={message.kind === 'error' ? 'alert' : 'status'} className={message.kind === 'error' ? errorClass : okClass}>{message.text}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy || !dirty} className={primaryButtonClass}>{busy ? t('common.saving') : t('common.save')}</button>
          <button type="button" onClick={() => void remove()} disabled={busy} className={dangerButtonClass}>{t('offerAdmin.deleteCategory')}</button>
        </div>
      </form>

      {!category.is_active && <p className={mutedClass}>{t('offerAdmin.categoryHidden')}</p>}
      <ul className="divide-y divide-slate-200 dark:divide-slate-800">
        {category.items.map((item, index) => (
          <ItemEditor
            key={item.id}
            item={item}
            categories={categories}
            currency={currency}
            first={index === 0}
            last={index === category.items.length - 1}
            onMove={(delta) => void moveItem(index, delta)}
            onChanged={onChanged}
          />
        ))}
      </ul>
      {category.items.length === 0 && <p className={mutedClass}>{t('offerAdmin.noItems')}</p>}
      {adding ? (
        <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
          <ItemForm
            categoryId={category.id}
            categories={categories}
            onSaved={() => {
              setAdding(false)
              onChanged()
            }}
            onCancel={() => setAdding(false)}
          />
        </div>
      ) : (
        <button type="button" onClick={() => setAdding(true)} className={secondaryButtonClass}>{t('offerAdmin.addItem')}</button>
      )}
    </Section>
  )
}

function ItemEditor({ item, categories, currency, first, last, onMove, onChanged }: { item: ItemAdmin; categories: CategoryAdmin[]; currency: string; first: boolean; last: boolean; onMove: (delta: number) => void; onChanged: () => void }) {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  const [open, setOpen] = useState(false)
  const summary = item.prices.map((price) => `${price.label ? `${price.label} ` : ''}${formatPrice(price.price, currency, language)}`).join(' · ')

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className={`font-medium ${item.is_active ? '' : 'text-slate-500 line-through dark:text-slate-400'}`}>
            {item.name}
            {!item.is_active && <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-xs font-normal no-underline dark:border-slate-600">{t('offerAdmin.hidden')}</span>}
            {item.is_active && !item.is_available && <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-xs font-normal dark:border-slate-600">{t('offerAdmin.soldOut')}</span>}
          </p>
          <p className={mutedClass}>{summary || t('offerAdmin.noPrice')}</p>
        </div>
        <div className="flex gap-1">
          <button type="button" onClick={() => onMove(-1)} disabled={first} aria-label={t('offerAdmin.moveItemUp', { name: item.name })} className={secondaryButtonClass}>↑</button>
          <button type="button" onClick={() => onMove(1)} disabled={last} aria-label={t('offerAdmin.moveItemDown', { name: item.name })} className={secondaryButtonClass}>↓</button>
          <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className={secondaryButtonClass}>{open ? t('common.close') : t('offerAdmin.edit')}</button>
        </div>
      </div>
      {open && (
        <div className="mt-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
          <ItemForm
            item={item}
            categoryId={item.category_id}
            categories={categories}
            onSaved={() => {
              setOpen(false)
              onChanged()
            }}
            onCancel={() => setOpen(false)}
            onDeleted={onChanged}
          />
        </div>
      )}
    </li>
  )
}

interface PriceRow {
  key: string
  label: string
  price: string
}

let priceCounter = 0
const newPriceRow = (label = '', price = ''): PriceRow => ({ key: `price-${(priceCounter += 1)}`, label, price })

interface ItemFormProps {
  item?: ItemAdmin
  categoryId: string
  categories: CategoryAdmin[]
  onSaved: () => void
  onCancel: () => void
  onDeleted?: () => void
}

/** Creates an item (no `item`) or edits one - name, description, allergens, prices, flags and the category it belongs to. */
function ItemForm({ item, categoryId, categories, onSaved, onCancel, onDeleted }: ItemFormProps) {
  const { t } = useTranslation('pub_menu')
  const id = item?.id ?? `new-${categoryId}`
  const [name, setName] = useState(item?.name ?? '')
  const [description, setDescription] = useState(item?.description ?? '')
  const [allergens, setAllergens] = useState<number[]>(item?.allergens ?? [])
  const [prices, setPrices] = useState<PriceRow[]>(() => (item ? item.prices.map((price) => newPriceRow(price.label, priceText(price.price))) : [newPriceRow()]))
  const [available, setAvailable] = useState(item?.is_available ?? true)
  const [active, setActive] = useState(item?.is_active ?? true)
  const [category, setCategory] = useState(categoryId)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function changePrice(key: string, patch: Partial<PriceRow>) {
    setPrices((previous) => previous.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    const filled = prices.filter((row) => row.label.trim() !== '' || row.price.trim() !== '')
    const parsed = filled.map((row) => ({ label: row.label.trim(), price: parsePrice(row.price) }))
    if (parsed.some((row) => row.price === null || row.price < 0)) {
      setError(t('itemForm.priceInvalid'))
      return
    }
    setBusy(true)
    setError(null)
    const body = { name: name.trim(), description: description.trim(), allergens, is_available: available, is_active: active, prices: parsed }
    try {
      if (item) {
        await sendJson<ItemAdmin>(`${API_BASE}/manage/items/${item.id}`, 'PATCH', { ...body, ...(category !== item.category_id ? { category_id: category } : {}) })
      } else {
        await sendJson<ItemAdmin>(`${API_BASE}/manage/items`, 'POST', { ...body, category_id: category })
      }
      onSaved()
    } catch (err) {
      setError(statusOf(err) === 422 && Object.keys(errorsOf(err)).length > 0 ? t('itemForm.invalid') : t('errors.generic'))
      setBusy(false)
    }
  }

  async function remove() {
    if (!item || !window.confirm(t('itemForm.deleteConfirm', { name: item.name }))) return
    setBusy(true)
    try {
      await fetchJson<void>(`${API_BASE}/manage/items/${item.id}`, { method: 'DELETE' })
      onDeleted?.()
    } catch {
      setError(t('errors.generic'))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} className="space-y-3">
      <div>
        <label htmlFor={`${id}-name`} className={labelClass}>{t('itemForm.name')}</label>
        <input id={`${id}-name`} required maxLength={150} value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
      </div>
      <div>
        <label htmlFor={`${id}-description`} className={labelClass}>{t('itemForm.description')}</label>
        <input id={`${id}-description`} maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)} className={inputClass} />
      </div>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm text-slate-600 dark:text-slate-400">{t('itemForm.prices')}</legend>
        {prices.map((row) => (
          <div key={row.key} className="flex flex-wrap items-center gap-2">
            <input aria-label={t('itemForm.portion')} maxLength={50} value={row.label} onChange={(e) => changePrice(row.key, { label: e.target.value })} placeholder={t('itemForm.portionPlaceholder')} className={`${smallInputClass} w-32`} />
            <input aria-label={t('itemForm.price')} inputMode="decimal" value={row.price} onChange={(e) => changePrice(row.key, { price: e.target.value })} placeholder={t('itemForm.price')} className={`${smallInputClass} w-24`} />
            <button type="button" onClick={() => setPrices((previous) => previous.filter((entry) => entry.key !== row.key))} aria-label={t('itemForm.removePrice')} className={dangerButtonClass}>×</button>
          </div>
        ))}
        {prices.length < 6 && (
          <button type="button" onClick={() => setPrices((previous) => [...previous, newPriceRow()])} className={secondaryButtonClass}>{t('itemForm.addPrice')}</button>
        )}
        {prices.length === 0 && <p className={mutedClass}>{t('offerAdmin.noPrice')}</p>}
      </fieldset>
      <AllergenPicker idPrefix={id} value={allergens} onChange={setAllergens} />
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={available} onChange={(e) => setAvailable(e.target.checked)} />
          {t('itemForm.available')}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          {t('itemForm.active')}
        </label>
        {categories.length > 1 && (
          <div>
            <label htmlFor={`${id}-category`} className={labelClass}>{t('itemForm.category')}</label>
            <select id={`${id}-category`} value={category} onChange={(e) => setCategory(e.target.value)} className={smallInputClass}>
              {categories.map((entry) => (
                <option key={entry.id} value={entry.id}>{entry.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>
      {error && <p role="alert" className={errorClass}>{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? t('common.saving') : item ? t('common.save') : t('itemForm.create')}</button>
        <button type="button" onClick={onCancel} disabled={busy} className={secondaryButtonClass}>{t('common.cancel')}</button>
        {item && <button type="button" onClick={() => void remove()} disabled={busy} className={dangerButtonClass}>{t('itemForm.delete')}</button>}
      </div>
    </form>
  )
}
