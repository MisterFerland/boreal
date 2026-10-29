import type { Locale } from './types'
/** No binary floating point: amounts remain decimal strings; Intl only sees the integral BigInt. */
export function money(value: string | null | undefined, locale: Locale = 'en-CA'): string {
  if (value == null) return '—'
  const match = /^([+-]?)(\d+)(?:\.(\d{1,2}))?$/.exec(value)
  if (!match) return value
  const whole = new Intl.NumberFormat(locale).format(BigInt(match[2]))
  const decimal = locale === 'fr-CA' ? ',' : '.'
  const amount = `${match[1] === '-' ? '−' : ''}${whole}${decimal}${(match[3] || '').padEnd(2, '0')}`
  return locale === 'fr-CA' ? `${amount} $` : `$${amount}`
}
export function date(value: string | undefined, locale: Locale): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(locale, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'America/Toronto',
      }).format(parsed)
}
export function short(value: string | undefined, size = 12) {
  return value ? (value.length > size ? `${value.slice(0, size)}…` : value) : '—'
}
