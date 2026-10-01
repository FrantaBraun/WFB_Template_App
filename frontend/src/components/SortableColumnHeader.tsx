/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

interface SortableColumnHeaderProps<T extends string> {
  label: string
  column: T
  activeColumn: T
  direction: 'asc' | 'desc'
  onSort: (column: T) => void
}

/** A clickable <th> for the admin Pages list table - kept generic since
 * any admin list needs the same click-to-sort-toggle-direction header. */
export default function SortableColumnHeader<T extends string>({
  label,
  column,
  activeColumn,
  direction,
  onSort,
}: SortableColumnHeaderProps<T>) {
  return (
    <th className="py-2 font-medium">
      <button
        type="button"
        onClick={() => onSort(column)}
        className="flex items-center gap-1 hover:text-slate-900 dark:hover:text-slate-100"
      >
        {label}
        {activeColumn === column && <span aria-hidden="true">{direction === 'asc' ? '▲' : '▼'}</span>}
      </button>
    </th>
  )
}
