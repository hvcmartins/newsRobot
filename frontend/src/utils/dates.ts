/**
 * Parse a datetime string from the API, treating timezone-naive strings as UTC.
 *
 * The backend stores UTC datetimes in SQLite without timezone info. Pydantic
 * serialises them with "+00:00" where schemas are in place, but raw dict
 * endpoints and older code may still emit naive strings like
 * "2026-06-04T12:00:00". JavaScript's Date constructor interprets those as
 * LOCAL time, which causes timestamps to be off by the browser's UTC offset.
 *
 * This function appends "Z" to any string that has no timezone indicator,
 * guaranteeing correct UTC parsing across all browsers and all code paths.
 */
export function parseUTC(dateStr: string | null | undefined): Date {
  if (!dateStr) return new Date(NaN)
  // Already has timezone info (ends with Z or ±HH:MM / ±HHMM)
  if (/Z$|[+-]\d{2}:?\d{2}$/.test(dateStr)) {
    return new Date(dateStr)
  }
  return new Date(dateStr + 'Z')
}
