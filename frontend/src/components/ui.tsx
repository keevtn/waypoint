// Small shared primitives. One accent color; semantic colors only for flags.
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Card({
  children,
  className = "",
  title,
  aside,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  aside?: ReactNode;
}) {
  return (
    <section className={`rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {(title || aside) && (
        <header className="mb-3 flex items-baseline justify-between gap-2">
          {title && <h2 className="text-xs font-medium text-slate-500 dark:text-slate-400">{title}</h2>}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export type Tone = "neutral" | "accent" | "warn" | "danger" | "ok";

export function Stat({ label, value, sub, tone = "neutral" }: { label: string; value: string; sub?: ReactNode; tone?: Tone }) {
  const color = {
    neutral: "text-slate-900 dark:text-slate-100",
    accent: "text-accent dark:text-accent-light",
    warn: "text-warn dark:text-amber-300",
    danger: "text-danger dark:text-red-300",
    ok: "text-ok dark:text-green-300",
  }[tone];
  return (
    <div>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`tabular mt-1 text-3xl font-semibold leading-none tracking-tightest ${color}`}>{value}</div>
      {sub && <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{sub}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded bg-slate-200 dark:bg-slate-800 ${className}`} />;
}

export function SkeletonLines({ n = 3 }: { n?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: n }, (_, i) => (
        <Skeleton key={i} className={`h-3 ${i === n - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

type Variant = "primary" | "secondary" | "ghost";
export function Button({
  variant = "primary",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded px-3.5 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-white hover:bg-[#0b4a48] dark:bg-accent-light dark:text-slate-950 dark:hover:bg-[#56b3ad]",
    secondary:
      "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800",
    ghost: "text-accent hover:bg-accent-soft dark:text-accent-light dark:hover:bg-slate-800",
  };
  return <button className={`${base} ${styles[variant]} ${className}`} {...rest} />;
}

const toneClass: Record<Tone, string> = {
  neutral: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
  accent: "border-accent/30 bg-accent-soft text-accent dark:border-accent-light/40 dark:bg-slate-800 dark:text-accent-light",
  warn: "border-warn/40 bg-amber-50 text-warn dark:bg-amber-950/40 dark:text-amber-300",
  danger: "border-danger/40 bg-red-50 text-danger dark:bg-red-950/40 dark:text-red-300",
  ok: "border-ok/40 bg-green-50 text-ok dark:bg-green-950/40 dark:text-green-300",
};

export function Badge({
  tone = "neutral",
  children,
  title,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] font-medium leading-4 ${toneClass[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone, className = "" }: { tone: Tone; className?: string }) {
  const c = { neutral: "bg-slate-400", accent: "bg-accent", warn: "bg-warn", danger: "bg-danger", ok: "bg-ok" }[tone];
  return <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-full ${c} ${className}`} />;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-danger/40 bg-red-50 px-3 py-2 text-sm text-danger dark:bg-red-950/40 dark:text-red-300"
    >
      {message}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500 dark:text-slate-400 dark:border-slate-800 dark:bg-slate-900">
      {children}
    </div>
  );
}

export const inputClass =
  "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm tabular placeholder:text-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent dark:border-slate-700 dark:bg-slate-950 dark:focus:border-accent-light dark:focus:ring-accent-light";

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}
    </label>
  );
}
