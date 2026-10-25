// Overview: connect → balance, income, recurring (confidence dots), variable spend, slack, baseline chart.
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { Profile, RecurringItem } from "../types";
import { centsToDollarsText, dollarsToCents, fmtCadence, fmtCents, fmtDate, fmtDollars, fmtPct } from "../lib/format";
import { errorMessage } from "../lib/hooks";
import { markConnected } from "../lib/session";
import ProjectionChart, { BASELINE_KEY } from "../components/ProjectionChart";
import { Badge, Button, Card, Dot, ErrorNote, Skeleton, Stat, inputClass, type Tone } from "../components/ui";
import { BalanceEditor, ListEditorCard, resetToDemo } from "../components/ProfileEditors";
import HorizonSelect, { HorizonNote } from "../components/HorizonSelect";
import CsvImport from "../components/CsvImport";

const confidenceTone = (c: number): Tone => (c >= 0.9 ? "ok" : c >= 0.7 ? "warn" : "neutral");

export default function Overview() {
  const navigate = useNavigate();
  const { profile, baseline, setProfile, setBaseline } = useAppState();
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [institution, setInstitution] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  const reset = async () => {
    if (!window.confirm("Reset to the demo account? Your edits will be discarded.")) return;
    setResetting(true);
    setResetError(null);
    try {
      await resetToDemo();
    } catch (e) {
      setResetError(errorMessage(e));
    } finally {
      setResetting(false);
    }
  };

  const connect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const c = await api.connect();
      setInstitution(c.institution);
      markConnected();
      const [p, b] = await Promise.all([api.profile(), api.baseline(useAppState.getState().horizonMonths)]);
      setProfile(p);
      setBaseline(b);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setConnecting(false);
    }
  };

  if (!profile) {
    return (
      <section className="mx-auto max-w-2xl py-10">
        <h1 className="text-2xl font-semibold tracking-tight">Decide with your real cash flow, not a guess.</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
          Connect a checking account to get a 12-month projection from your income, bills, and spending, then test a decision against it.
        </p>
        <div className="mt-6 flex items-center gap-3">
          <Button onClick={connect} disabled={connecting}>
            {connecting ? "Connecting…" : "Connect your bank"}
          </Button>
          <span className="text-xs text-slate-500 dark:text-slate-400">Demo bank · Plaid sandbox</span>
          <CsvImport onImported={(n) => setInstitution(`Imported CSV · ${n} transactions`)} />
        </div>
        {connecting && (
          <div className="mt-6 space-y-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        )}
        {error && (
          <div className="mt-4">
            <ErrorNote message={error} />
          </div>
        )}
        <ul className="mt-10 grid gap-3 text-sm text-slate-600 dark:text-slate-300 sm:grid-cols-3">
          <li className="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="font-medium text-slate-900 dark:text-slate-100">Numbers come from code</div>
            The model never produces a figure you act on.
          </li>
          <li className="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="font-medium text-slate-900 dark:text-slate-100">Facts come with sources</div>
            Every claim links to a regulator or non-profit page.
          </li>
          <li className="rounded-md border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="font-medium text-slate-900 dark:text-slate-100">No carrier, no bank</div>
            You get a configuration, not a product.
          </li>
        </ul>
      </section>
    );
  }

  const sortedOneOffs = [...profile.one_offs].sort((a, b) => a.date.localeCompare(b.date));
  const upcoming = sortedOneOffs.filter((o) => o.date >= profile.as_of);
  const past = sortedOneOffs.filter((o) => o.date < profile.as_of);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your cash flow</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {institution ?? "Demo bank · Plaid sandbox"} · as of {fmtDate(profile.as_of)}
          </p>
        </div>
        <Button onClick={() => navigate("/moment")} variant="primary">
          Pick a decision
        </Button>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <BalanceEditor profile={profile} />
        </Card>
        <Card>
          <Stat
            label="Monthly slack"
            value={fmtCents(profile.monthly_slack_cents)}
            tone={profile.monthly_slack_cents < 0 ? "danger" : "ok"}
            sub="Income minus bills and typical spending"
          />
        </Card>
        <Card>
          <Stat
            label="Variable spend"
            value={`${fmtDollars(profile.variable.mean_monthly_cents)} / mo`}
            sub={
              <>
                ± {fmtDollars(profile.variable.std_monthly_cents)} · <span className="tabular">{profile.variable.months_observed}</span> months observed
              </>
            }
          />
        </Card>
        <Card>
          <FloorEditor profile={profile} onSaved={setProfile} />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ListEditorCard kind="income" profile={profile} className="lg:col-span-1">
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {profile.income.map((s) => (
              <li key={s.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                <div className="flex items-start gap-2">
                  <Dot tone={confidenceTone(s.confidence)} className="mt-1.5" />
                  <div>
                    <div className="font-medium">{s.label}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {fmtCadence(s.cadence)} · next {fmtDate(s.next_date)}
                    </div>
                  </div>
                </div>
                <div className="tabular shrink-0 font-medium text-ok">{fmtCents(s.amount_cents, { sign: true })}</div>
              </li>
            ))}
          </ul>
        </ListEditorCard>

        <ListEditorCard kind="recurring" profile={profile} className="lg:col-span-1" aside={<ConfidenceLegend />}>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {[...profile.recurring].sort((a, b) => a.amount_cents - b.amount_cents).map((r) => (
              <RecurringRow key={r.id} item={r} />
            ))}
          </ul>
        </ListEditorCard>

        <ListEditorCard
          kind="one_offs"
          profile={profile}
          className="lg:col-span-1"
          footnote={
            past.length > 0 && (
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                <span className="tabular">{past.length}</span> past one-time {past.length === 1 ? "cost" : "costs"} ({past.map((o) => o.label).join(", ")}) already in your balance.
              </p>
            )
          }
        >
          {upcoming.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">None.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {upcoming.map((o) => (
                <li key={o.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                  <div>
                    <div className="font-medium">{o.label}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {fmtDate(o.date)} ·{" "}
                      <Badge tone="neutral" className="align-middle">
                        {o.source === "user" ? "You added" : o.source === "module" ? "From decision" : "Detected"}
                      </Badge>
                    </div>
                  </div>
                  <div className="tabular shrink-0 font-medium">{fmtCents(o.amount_cents)}</div>
                </li>
              ))}
            </ul>
          )}
        </ListEditorCard>
      </div>

      <Card
        title="Baseline"
        aside={
          <span className="flex flex-wrap items-center gap-4">
            {baseline && (
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Lowest point <span className="tabular font-medium text-slate-700 dark:text-slate-200">{fmtCents(baseline.min_balance_cents)}</span> on{" "}
                {fmtDate(baseline.min_balance_date)}
              </span>
            )}
            <HorizonSelect id="horizon-overview" />
          </span>
        }
      >
        {baseline ? (
          <ProjectionChart
            series={[{ id: BASELINE_KEY, label: "Baseline", result: baseline }]}
            selectedId={BASELINE_KEY}
            floorCents={profile.safety_floor_cents}
            height={260}
          />
        ) : (
          <Skeleton className="h-[260px]" />
        )}
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          End-of-month balance if your income, bills, one-time costs, and typical spending continue.
        </p>
        <HorizonNote source={baseline} />
      </Card>

      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          <button type="button" onClick={reset} disabled={resetting} className="hover:underline disabled:opacity-50">
            {resetting ? "Resetting…" : "Reset to demo account"}
          </button>
          {resetError && <span className="ml-2 text-danger">{resetError}</span>}
        </span>
        <Link to="/moment" className="text-sm font-medium text-accent hover:underline dark:text-accent-light">
          Pick a decision to test against this
        </Link>
      </div>
    </section>
  );
}

function RecurringRow({ item }: { item: RecurringItem }) {
  return (
    <li className="flex items-start justify-between gap-3 py-2 text-sm">
      <div className="flex items-start gap-2">
        <Dot tone={confidenceTone(item.confidence)} className="mt-1.5" />
        <div>
          <div className="font-medium">{item.label}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">
            {fmtCadence(item.cadence)} · next {fmtDate(item.next_date)} · {fmtPct(item.confidence)} confident
          </div>
        </div>
      </div>
      <div className="tabular shrink-0 font-medium">{fmtCents(item.amount_cents)}</div>
    </li>
  );
}

function ConfidenceLegend() {
  return (
    <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
      <span className="flex items-center gap-1">
        <Dot tone="ok" /> high
      </span>
      <span className="flex items-center gap-1">
        <Dot tone="warn" /> medium
      </span>
      <span className="flex items-center gap-1">
        <Dot tone="neutral" /> low
      </span>
    </span>
  );
}

function FloorEditor({ profile, onSaved }: { profile: Profile; onSaved: (p: Profile) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(centsToDollarsText(profile.safety_floor_cents));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const cents = dollarsToCents(text);
    if (cents === null || cents < 0) {
      setError("Enter a dollar amount.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const p = await api.updateProfile({ safety_floor_cents: cents });
      onSaved(p);
      try {
        useAppState.getState().setBaseline(await api.baseline(useAppState.getState().horizonMonths));
      } catch {
        /* keep the old baseline if the refetch fails */
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
        label="Safety floor"
        value={fmtCents(profile.safety_floor_cents)}
        sub={
          <>
            The balance you never want to drop below.{" "}
            <button type="button" onClick={() => setEditing(true)} className="text-sm font-medium text-accent hover:underline dark:text-accent-light">
              Edit
            </button>
          </>
        }
      />
    );
  }
  return (
    <form onSubmit={save}>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Safety floor</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-sm text-slate-500 dark:text-slate-400">$</span>
        <input className={inputClass} value={text} onChange={(e) => setText(e.target.value)} inputMode="decimal" autoFocus aria-label="Safety floor in dollars" />
      </div>
      <div className="mt-2 flex gap-2">
        <Button type="submit" disabled={saving} className="px-2.5 py-1 text-xs">
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="secondary" onClick={() => setEditing(false)} className="px-2.5 py-1 text-xs">
          Cancel
        </Button>
      </div>
      {error && <div className="mt-1 text-xs text-danger">{error}</div>}
    </form>
  );
}
