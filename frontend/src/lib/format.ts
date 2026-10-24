// Formatting at the edge. Money is integer cents everywhere else.
import type { Cadence } from "../types";

const MINUS = "−";

export const fmtCents = (cents: number, opts: { sign?: boolean } = {}): string => {
  const abs = Math.abs(cents) / 100;
  const s = abs.toLocaleString("en-US", { style: "currency", currency: "USD" });
  if (cents < 0) return `${MINUS}${s}`;
  return opts.sign ? `+${s}` : s;
};

/** Whole dollars, no cents: "$1,240". */
export const fmtDollars = (cents: number): string => {
  const abs = Math.round(Math.abs(cents) / 100);
  const s = abs.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  return cents < 0 ? `${MINUS}${s}` : s;
};

/** "2027-01" -> "Jan 2027" */
export const fmtMonth = (month: string): string => {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
};

/** "2027-01" -> "Jan" */
export const fmtMonthShort = (month: string): string => {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
};

/** "2026-11-05" -> "Nov 5, 2026" */
export const fmtDate = (iso: string): string => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
};

export const fmtCadence = (c: Cadence): string =>
  ({ weekly: "Weekly", biweekly: "Every 2 weeks", semimonthly: "Twice a month", monthly: "Monthly", once: "One time" })[c];

export const fmtPct = (x: number): string => `${Math.round(x * 100)}%`;

/** Add n days to an ISO date string. */
export const addDays = (iso: string, n: number): string => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};

export const todayIso = (): string => new Date().toISOString().slice(0, 10);

/** Dollars text field -> cents, or null when blank/invalid. */
export const dollarsToCents = (s: string): number | null => {
  const t = s.replace(/[$,\s]/g, "");
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? Math.round(n * 100) : null;
};

export const centsToDollarsText = (cents: number | null): string => (cents === null ? "" : String(cents / 100));
