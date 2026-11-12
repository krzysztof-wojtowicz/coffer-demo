import { cn } from '../lib/cn'

/** Coffee mug with a bundle of banknotes sticking out. Colours come from theme tokens. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={cn('size-7 shrink-0', className)}
    >
      <g transform="rotate(-14 11 10)">
        <rect x="7" y="2" width="9" height="14" rx="1.5" className="fill-positive" />
      </g>
      <g transform="rotate(12 19 10)">
        <rect x="15" y="3" width="9" height="13" rx="1.5" className="fill-positive" />
      </g>
      <rect x="11" y="1.5" width="9" height="14" rx="1.5" className="fill-positive" />
      <circle cx="15.5" cy="8" r="2.4" className="fill-surface" opacity=".6" />
      <path d="M4 14h20v8a7 7 0 0 1-7 7h-6a7 7 0 0 1-7-7z" className="fill-accent" />
      <path
        d="M24 17h2.5a3 3 0 0 1 0 6H23.5"
        fill="none"
        strokeWidth="2.6"
        strokeLinecap="round"
        className="stroke-accent"
      />
      <rect x="3" y="13" width="22" height="3" rx="1.5" className="fill-accent-strong" />
    </svg>
  )
}
