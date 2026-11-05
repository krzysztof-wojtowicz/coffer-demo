export function ErrorMessage({ message }: { message?: string | null }) {
  if (!message) return null
  return (
    <p className="text-sm text-negative" role="alert">
      {message}
    </p>
  )
}
