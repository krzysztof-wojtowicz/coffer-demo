export type SseEvent = { event: string; data: string }

/** Parsuje fragment strumienia SSE. `buffer` to niedokończone dane z poprzedniego wywołania. */
export function parseSse(chunk: string, buffer: string): { events: SseEvent[]; rest: string } {
  const parts = (buffer + chunk).replace(/\r\n/g, '\n').split('\n\n')
  const rest = parts.pop() ?? ''
  const events: SseEvent[] = []
  for (const block of parts) {
    let event = 'message'
    const data: string[] = []
    let hasData = false
    for (const line of block.split('\n')) {
      if (line === '' || line.startsWith(':')) continue
      const idx = line.indexOf(':')
      const field = idx === -1 ? line : line.slice(0, idx)
      let value = idx === -1 ? '' : line.slice(idx + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') {
        data.push(value)
        hasData = true
      }
    }
    if (hasData) events.push({ event, data: data.join('\n') })
  }
  return { events, rest }
}
