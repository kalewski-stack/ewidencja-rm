// Wszystkie teksty interfejsu w content/i18n/pl.json. Struktura gotowa pod kolejne języki.
import pl from '@content/i18n/pl.json';

const dict = pl as Record<string, string>;

export function t(key: string, vars?: Record<string, string | number>): string {
  let s = dict[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}
