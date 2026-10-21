/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

/** The pub's mark: a mug of lager under a head of foam. Drawn in `currentColor` (the outline) plus the beer's own amber. */
export function PubLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" className={className}>
      <path d="M10 19h22v21a3 3 0 0 1-3 3H13a3 3 0 0 1-3-3Z" fill="var(--color-beer)" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
      <path d="M32 23h3.5a5.5 5.5 0 0 1 5.5 5.5v3A5.5 5.5 0 0 1 35.5 37H32" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M16 26v12M21 26v12M26 26v12" stroke="#fffaf0" strokeOpacity="0.55" strokeWidth="2" strokeLinecap="round" />
      <path
        d="M8.5 19c-1.8-4.6 2.4-8 5.8-6.2C15.8 8.7 21.5 8 23.3 11.6c3.2-1.9 8.2-.2 8.4 4.1 2 .1 3.2 1.4 3.2 3.3Z"
        fill="#fffaf0"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** A hop cone with its leaf - the sign of the pub's name. */
export function HopIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <path d="M12 2.5c.6 1.4 2 2.2 3.4 2.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path
        d="M12 5c3.4 0 6 2.9 6 7s-2.6 9.5-6 9.5S6 16.1 6 12s2.6-7 6-7Z"
        fill="currentColor"
        fillOpacity="0.18"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M6.6 10c2 1.4 3.8 1.6 5.4.4 1.6 1.2 3.4 1 5.4-.4M6.2 14c2 1.4 3.9 1.6 5.8.4 1.9 1.2 3.8 1 5.8-.4M7.4 18c1.6 1 3.2 1.1 4.6.2 1.4.9 3 .8 4.6-.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

/** A thin rule with a hop cone in the middle, to part the sections of a page. */
export function Ornament({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 text-hop dark:text-hop-dark ${className}`} role="presentation">
      <span className="h-px flex-1 bg-current opacity-30" />
      <HopIcon className="h-6 w-6" />
      <span className="h-px flex-1 bg-current opacity-30" />
    </div>
  )
}
