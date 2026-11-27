import { cn } from '../lib/cn'

/** Coffee cup with one banknote sticking out. Single colour: follows the text colour (white by default). */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={cn('size-7 shrink-0 text-white', className)}
      fill="currentColor"
    >
      {/* Banknote: rounded rectangle with a coin-shaped hole, tilted. */}
      <path
        fillRule="evenodd"
        transform="rotate(-8 14 7)"
        d="M7.5 1.5h13a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 6 11V3a1.5 1.5 0 0 1 1.5-1.5zM14 4.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6z"
      />
      <path d="M4 14.5h20v7.5a7 7 0 0 1-7 7h-6a7 7 0 0 1-7-7z" />
      <path d="M24 17.5h2.2a3 3 0 0 1 0 6H23.5" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}
