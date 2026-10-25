// In-place editors for the demo profile on Overview. Edits are staged locally per card and sent as one
// PUT /profile on Save; Cancel discards. After a save the profile and baseline are refetched and any cached
// evaluation is cleared so Compare re-runs on the current numbers. Amounts are entered as positive dollars;
// outflows (recurring, one-time costs) are stored as negative cents, matching the profile's sign convention.
import { useState, type ReactNode } from "react";
import { api } from "../api";
import { useAppState } from "../state";
import type { Cadence, IncomeStream, OneOff, Profile, RecurringItem } from "../types";
import { centsToDollarsText, dollarsToCents, fmtCents } from "../lib/format";
import { errorMessage } from "../lib/hooks";
import { Button, Card, Stat, inputClass } from "./ui";

const CADENCES: { value: Cadence; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Every 2 weeks" },
  { value: "semimonthly", label: "Twice a month" },
  { value: "monthly", label: "Monthly" },
];

const isIsoDate = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));
const newId = (prefix: string) => `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

/** Send one PUT /profile, then refetch profile + baseline and drop any cached evaluation. */
export async function saveProfilePatch(patch: Partial<Pick<Profile, "balance_cents" | "income" | "recurring" | "one_offs" | "safety_floor_cents">>): Promise<Profile> {
  await api.updateProfile(patch);
  const [p, b] = await Promise.all([api.profile(), api.baseline(useAppState.getState().horizonMonths)]);
  const st = useAppState.getState();
  st.setProfile(p);
  st.setBaseline(b);
  if (st.evaluation) st.setEvaluation(null);
  return p;
}

const NOT_ACCEPTED = "Not saved: the server does not accept this change yet.";
const rowKey = (r: { id: string; amount_cents: number }) => `${r.id}:${r.amount_cents}`;
const sameRows = (a: { id: string; amount_cents: number }[], b: { id: string; amount_cents: number }[]) =>
  a.length === b.length && a.map(rowKey).sort().join("|") === b.map(rowKey).sort().join("|");

/** Replace the profile with the demo account: POST /bank/connect, then refetch. */
export async function resetToDemo() {
  await api.connect();
  const [p, b] = await Promise.all([api.profile(), api.baseline(useAppState.getState().horizonMonths)]);
  const st = useAppState.getState();
  st.setProfile(p);
  st.setBaseline(b);
  if (st.evaluation) st.setEvaluation(null);
}

export function EditLink({ onClick, children = "Edit" }: { onClick: () => void; children?: ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="text-sm font-medium text-accent hover:underline dark:text-accent-light">
      {children}
    </button>
  );
}

function FormFooter({ saving, error, onCancel }: { saving: boolean; error: string | null; onCancel: () => void }) {
  return (
    <div className="mt-3 flex items-center gap-2">
      <Button type="submit" disabled={saving} className="px-2.5 py-1 text-xs">
        {saving ? "Saving…" : "Save"}
      </Button>
      <Button type="button" variant="secondary" onClick={onCancel} className="px-2.5 py-1 text-xs">
        Cancel
      </Button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}

const Err = ({ msg }: { msg?: string }) => (msg ? <div className="mt-1 text-xs text-danger">{msg}</div> : null);

// ---------- Balance ----------

export function BalanceEditor({ profile }: { profile: Profile }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(centsToDollarsText(profile.balance_cents));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();

  const open = () => {
    setText(centsToDollarsText(profile.balance_cents));
    setFieldError(undefined);
    setError(null);
    setEditing(true);
  };
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const cents = dollarsToCents(text);
    if (cents === null || cents < 0) {
      setFieldError("Enter a dollar amount of 0 or more.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const p = await saveProfilePatch({ balance_cents: cents });
      if (p.balance_cents !== cents) {
        setError(NOT_ACCEPTED);
        return;
      }
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <Stat
        label="Current balance"
        value={fmtCents(profile.balance_cents)}
        sub={
          <>
            Checking. <EditLink onClick={open} />
          </>
        }
      />
    );
  }
  return (
    <form onSubmit={save} noValidate>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Current balance</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-sm text-slate-500 dark:text-slate-400">$</span>
        <input className={inputClass} value={text} onChange={(e) => setText(e.target.value)} inputMode="decimal" autoFocus aria-label="Current balance in dollars" />
      </div>
      <Err msg={fieldError} />
      <FormFooter saving={saving} error={error} onCancel={() => setEditing(false)} />
    </form>
  );
}

// ---------- Row editors (income, recurring, one-time costs) ----------

interface Row {
  id: string;
  label: string;
  amount: string; // positive dollars as typed
  cadence: Cadence;
  date: string;
  readOnly?: boolean;
}

type Kind = "income" | "recurring" | "one_offs";

const KIND: Record<Kind, { title: string; withCadence: boolean; outflow: boolean; dateLabel: string; addLabel: string; empty: string }> = {
  income: { title: "Income", withCadence: true, outflow: false, dateLabel: "Next date", addLabel: "Add income", empty: "At least one income stream is required." },
  recurring: { title: "Recurring payments", withCadence: true, outflow: true, dateLabel: "Next date", addLabel: "Add payment", empty: "" },
  one_offs: { title: "Upcoming one-time costs", withCadence: false, outflow: true, dateLabel: "Date", addLabel: "Add cost", empty: "" },
};

function rowsFor(kind: Kind, profile: Profile): Row[] {
  if (kind === "income") return profile.income.map((s) => ({ id: s.id, label: s.label, amount: centsToDollarsText(Math.abs(s.amount_cents)), cadence: s.cadence, date: s.next_date }));
  if (kind === "recurring") return profile.recurring.map((r) => ({ id: r.id, label: r.label, amount: centsToDollarsText(Math.abs(r.amount_cents)), cadence: r.cadence, date: r.next_date }));
  // Past detected one-offs stay read-only (they live in the card's footnote); only upcoming ones are edited here.
  return profile.one_offs
    .filter((o) => o.date >= profile.as_of)
    .map((o) => ({ id: o.id, label: o.label, amount: centsToDollarsText(Math.abs(o.amount_cents)), cadence: "once" as Cadence, date: o.date }));
}

function blankRow(kind: Kind, asOf: string): Row {
  return { id: newId(kind), label: "", amount: "", cadence: kind === "one_offs" ? "once" : "monthly", date: asOf };
}

/**
 * Card with a list in view mode and a row editor in edit mode. `children` is the read-only rendering;
 * `footnote` stays visible in both modes (past one-offs).
 */
export function ListEditorCard({
  kind,
  profile,
  aside,
  className = "",
  children,
  footnote,
}: {
  kind: Kind;
  profile: Profile;
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
  footnote?: ReactNode;
}) {
  const meta = KIND[kind];
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [listError, setListError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = () => {
    setRows(rowsFor(kind, profile));
    setErrors({});
    setListError(null);
    setError(null);
    setEditing(true);
  };
  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const remove = (i: number) => setRows((rs) => rs.filter((_, j) => j !== i));
  const add = () => setRows((rs) => [...rs, blankRow(kind, profile.as_of)]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    rows.forEach((r, i) => {
      const cents = dollarsToCents(r.amount);
      if (!r.label.trim()) errs[`${i}.label`] = "Give it a name.";
      if (cents === null || cents <= 0) errs[`${i}.amount`] = "Enter an amount above 0.";
      if (!isIsoDate(r.date)) errs[`${i}.date`] = "Enter a date.";
    });
    const le = kind === "income" && rows.length === 0 ? meta.empty : null;
    setErrors(errs);
    setListError(le);
    if (Object.keys(errs).length > 0 || le) return;

    setSaving(true);
    setError(null);
    try {
      if (kind === "income") {
        const prev = new Map(profile.income.map((s) => [s.id, s]));
        const income: IncomeStream[] = rows.map((r) => ({
          id: r.id,
          label: r.label.trim(),
          amount_cents: dollarsToCents(r.amount) as number,
          cadence: r.cadence,
          next_date: r.date,
          confidence: prev.get(r.id)?.confidence ?? 1,
        }));
        const p = await saveProfilePatch({ income });
        if (!sameRows(p.income, income)) return setError(NOT_ACCEPTED);
      } else if (kind === "recurring") {
        const prev = new Map(profile.recurring.map((s) => [s.id, s]));
        const recurring: RecurringItem[] = rows.map((r) => ({
          id: r.id,
          label: r.label.trim(),
          amount_cents: -(dollarsToCents(r.amount) as number),
          cadence: r.cadence,
          next_date: r.date,
          confidence: prev.get(r.id)?.confidence ?? 1,
          category: prev.get(r.id)?.category ?? null,
        }));
        const p = await saveProfilePatch({ recurring });
        if (!sameRows(p.recurring, recurring)) return setError(NOT_ACCEPTED);
      } else {
        const prev = new Map(profile.one_offs.map((o) => [o.id, o]));
        const past = profile.one_offs.filter((o) => o.date < profile.as_of);
        const upcoming: OneOff[] = rows.map((r) => ({
          id: r.id,
          label: r.label.trim(),
          amount_cents: -(dollarsToCents(r.amount) as number),
          date: r.date,
          source: prev.get(r.id)?.source ?? "user",
        }));
        const p = await saveProfilePatch({ one_offs: [...past, ...upcoming] });
        if (!sameRows(p.one_offs, [...past, ...upcoming])) return setError(NOT_ACCEPTED);
      }
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card
      title={meta.title}
      className={className}
      aside={
        <span className="flex items-center gap-3">
          {aside}
          {!editing && <EditLink onClick={open} />}
        </span>
      }
    >
      {!editing ? (
        <>
          {children}
          {footnote}
        </>
      ) : (
        <form onSubmit={save} noValidate>
          <ul className="space-y-3">
            {rows.map((r, i) => (
              <li key={r.id} className="rounded-md bg-slate-50 p-3 dark:bg-slate-950/60">
                <div className={`grid gap-2 ${meta.withCadence ? "sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" : ""}`}>
                  <div>
                    <input className={inputClass} value={r.label} placeholder="Name" aria-label="Name" onChange={(e) => setRow(i, { label: e.target.value })} />
                    <Err msg={errors[`${i}.label`]} />
                  </div>
                  <div>
                    <div className="relative">
                      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-slate-500 dark:text-slate-400">$</span>
                      <input className={`${inputClass} pl-7`} inputMode="decimal" value={r.amount} aria-label="Amount in dollars" onChange={(e) => setRow(i, { amount: e.target.value })} />
                    </div>
                    <Err msg={errors[`${i}.amount`]} />
                  </div>
                </div>
                <div className={`mt-2 grid gap-2 ${meta.withCadence ? "sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" : ""}`}>
                  {meta.withCadence && (
                    <select className={inputClass} value={r.cadence} aria-label="Cadence" onChange={(e) => setRow(i, { cadence: e.target.value as Cadence })}>
                      {CADENCES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  )}
                  <div>
                    <input type="date" className={inputClass} value={r.date} aria-label={meta.dateLabel} onChange={(e) => setRow(i, { date: e.target.value })} />
                    <Err msg={errors[`${i}.date`]} />
                  </div>
                </div>
                <div className="mt-2 flex justify-end">
                  <button type="button" onClick={() => remove(i)} className="text-xs text-slate-500 hover:underline dark:text-slate-400">
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <button type="button" onClick={add} className="text-sm font-medium text-accent hover:underline dark:text-accent-light">
              {meta.addLabel}
            </button>
          </div>
          {listError && <div className="mt-2 text-xs text-danger">{listError}</div>}
          {footnote}
          <FormFooter saving={saving} error={error} onCancel={() => setEditing(false)} />
        </form>
      )}
    </Card>
  );
}
