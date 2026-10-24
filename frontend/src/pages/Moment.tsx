// Moment: module picker + hand-built auto insurance form (no generic schema renderer).
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { AutoInsuranceInputs, DecisionSummary, UserQuote } from "../types";
import { addDays, centsToDollarsText, dollarsToCents, fmtCents, todayIso } from "../lib/format";
import { errorMessage, useAsync } from "../lib/hooks";
import { Badge, Button, Card, ErrorNote, Field, Skeleton, inputClass } from "../components/ui";

interface FormState {
  vehicleValue: string;
  financed: boolean;
  loanPayment: string;
  loanTerm: string;
  driverAge: string;
  deductibleComfort: string;
  registrationDeadline: string;
  quotes: { label: string; monthly: string }[];
}

// Demo persona defaults (SPEC.md §8). The user can change any of them.
const defaultsFor = (asOf: string): FormState => ({
  vehicleValue: "9500",
  financed: true,
  loanPayment: "212",
  loanTerm: "48",
  driverAge: "21",
  deductibleComfort: "600",
  registrationDeadline: addDays(asOf, 30),
  quotes: [],
});

const fromInputs = (i: AutoInsuranceInputs): FormState => ({
  vehicleValue: centsToDollarsText(i.vehicle_value_cents),
  financed: i.financed,
  loanPayment: centsToDollarsText(i.loan_payment_cents),
  loanTerm: i.loan_term_months === null ? "" : String(i.loan_term_months),
  driverAge: String(i.driver_age),
  deductibleComfort: centsToDollarsText(i.deductible_comfort_cents),
  registrationDeadline: i.registration_deadline ?? "",
  quotes: i.user_quotes.map((q) => ({ label: q.label, monthly: centsToDollarsText(q.monthly_cents) })),
});

export default function Moment() {
  const navigate = useNavigate();
  const { profile, inputs, decisionId, setInputs, setEvaluation } = useAppState();
  const decisions = useAsync(() => api.decisions(), []);
  const [moduleId, setModuleId] = useState(decisionId);
  const [form, setForm] = useState<FormState>(() => (inputs ? fromInputs(inputs) : defaultsFor(profile?.as_of ?? todayIso())));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // If the profile arrives after first render, refresh the deadline default once.
  useEffect(() => {
    if (profile && !inputs) setForm((f) => ({ ...f, registrationDeadline: addDays(profile.as_of, 30) }));
  }, [profile, inputs]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const validate = (): AutoInsuranceInputs | null => {
    const e: Record<string, string> = {};
    const vehicle = dollarsToCents(form.vehicleValue);
    const comfort = dollarsToCents(form.deductibleComfort);
    const age = Number(form.driverAge);
    const loan = dollarsToCents(form.loanPayment);
    const term = form.loanTerm.trim() === "" ? null : Number(form.loanTerm);
    if (vehicle === null || vehicle < 0) e.vehicleValue = "Enter the car's value.";
    if (comfort === null || comfort < 0) e.deductibleComfort = "Enter an amount.";
    if (!Number.isInteger(age) || age < 16) e.driverAge = "Enter an age of 16 or older.";
    if (form.financed && (loan === null || loan <= 0)) e.loanPayment = "Enter your monthly loan payment.";
    if (form.financed && term !== null && (!Number.isInteger(term) || term < 1)) e.loanTerm = "Enter whole months.";
    const quotes: UserQuote[] = [];
    form.quotes.forEach((q, i) => {
      const c = dollarsToCents(q.monthly);
      if (!q.label.trim() || c === null || c <= 0) e[`quote${i}`] = "Give the quote a name and a monthly amount.";
      else quotes.push({ label: q.label.trim(), monthly_cents: c, attributes: {} });
    });
    setErrors(e);
    if (Object.keys(e).length > 0) return null;
    return {
      state: "PA",
      vehicle_value_cents: vehicle as number,
      financed: form.financed,
      loan_payment_cents: form.financed ? loan : null,
      loan_term_months: form.financed ? term : null,
      driver_age: age,
      deductible_comfort_cents: comfort as number,
      registration_deadline: form.registrationDeadline || null,
      user_quotes: quotes,
    };
  };

  const onSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    const parsed = validate();
    if (!parsed) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      setInputs(parsed);
      const result = await api.evaluate(moduleId, parsed);
      setEvaluation(result);
      navigate("/compare");
    } catch (e) {
      setSubmitError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">What are you deciding?</h1>
        <p className="text-sm text-slate-500">We run each option through your projection and tell you which months get tight.</p>
      </header>

      {!profile && (
        <div className="rounded-md border border-warn/40 bg-amber-50 px-3 py-2 text-sm text-warn dark:bg-amber-950/40 dark:text-amber-300">
          Connect your bank first so the options can be tested against your actual cash flow.{" "}
          <Link to="/" className="font-medium underline">
            Go to Overview
          </Link>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {decisions.loading && (
          <>
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </>
        )}
        {decisions.error && <ErrorNote message={decisions.error} />}
        {decisions.data?.map((d) => (
          <ModuleCard key={d.id} decision={d} selected={moduleId === d.id} onSelect={() => setModuleId(d.id)} />
        ))}
      </div>

      {moduleId === "auto_insurance" && (
        <Card title="Auto insurance · tell us about the car">
          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Vehicle value" hint="What you paid, or a current estimate.">
                <DollarInput value={form.vehicleValue} onChange={(v) => set("vehicleValue", v)} error={errors.vehicleValue} />
              </Field>
              <Field label="Driver age">
                <input className={inputClass} inputMode="numeric" value={form.driverAge} onChange={(e) => set("driverAge", e.target.value)} />
                <FieldError msg={errors.driverAge} />
              </Field>
            </div>

            <fieldset>
              <legend className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-200">Is the car financed?</legend>
              <div className="flex gap-2">
                <Choice active={form.financed} onClick={() => set("financed", true)}>
                  Yes, I have a loan
                </Choice>
                <Choice active={!form.financed} onClick={() => set("financed", false)}>
                  No, I own it outright
                </Choice>
              </div>
              <p className="mt-1 text-xs text-slate-500">Lenders usually set coverage requirements for a financed car; we check options against them.</p>
            </fieldset>

            {form.financed && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Monthly loan payment">
                  <DollarInput value={form.loanPayment} onChange={(v) => set("loanPayment", v)} error={errors.loanPayment} />
                </Field>
                <Field label="Loan term (months)" hint="Optional.">
                  <input className={inputClass} inputMode="numeric" value={form.loanTerm} onChange={(e) => set("loanTerm", e.target.value)} />
                  <FieldError msg={errors.loanTerm} />
                </Field>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Deductible you could pay on short notice" hint="If you had a claim next month, what could you cover without borrowing?">
                <DollarInput value={form.deductibleComfort} onChange={(v) => set("deductibleComfort", v)} error={errors.deductibleComfort} />
              </Field>
              <Field label="Registration deadline" hint="Optional. Sets the deadline on your action card.">
                <input type="date" className={inputClass} value={form.registrationDeadline} onChange={(e) => set("registrationDeadline", e.target.value)} />
              </Field>
            </div>

            <div>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Quotes you already have</span>
                <button
                  type="button"
                  onClick={() => set("quotes", [...form.quotes, { label: "", monthly: "" }])}
                  className="text-xs font-medium text-accent hover:underline dark:text-accent-light"
                >
                  Add a quote
                </button>
              </div>
              {form.quotes.length === 0 ? (
                <p className="text-xs text-slate-500">Optional. A real quote replaces our estimate for that configuration.</p>
              ) : (
                <ul className="space-y-2">
                  {form.quotes.map((q, i) => (
                    <li key={i} className="grid grid-cols-[1fr_8rem_auto] items-start gap-2">
                      <input
                        className={inputClass}
                        placeholder="Label, e.g. Independent agency A"
                        value={q.label}
                        onChange={(e) => set("quotes", form.quotes.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                      />
                      <DollarInput value={q.monthly} onChange={(v) => set("quotes", form.quotes.map((x, j) => (j === i ? { ...x, monthly: v } : x)))} placeholder="per month" />
                      <Button type="button" variant="ghost" onClick={() => set("quotes", form.quotes.filter((_, j) => j !== i))} className="px-2 py-2 text-xs">
                        Remove
                      </Button>
                      {errors[`quote${i}`] && <div className="col-span-3 text-xs text-danger">{errors[`quote${i}`]}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {submitError && <ErrorNote message={submitError} />}

            <div className="flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
              <span className="text-xs text-slate-500">
                Pennsylvania rules apply. {profile && <>Floor {fmtCents(profile.safety_floor_cents)}.</>}
              </span>
              <Button type="submit" disabled={submitting || !profile}>
                {submitting ? "Running projections…" : "Compare options"}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </section>
  );
}

function ModuleCard({ decision, selected, onSelect }: { decision: DecisionSummary; selected: boolean; onSelect: () => void }) {
  const soon = decision.id !== "auto_insurance";
  return (
    <button
      type="button"
      disabled={soon}
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "rounded-lg border p-4 text-left transition",
        soon ? "cursor-not-allowed border-slate-200 bg-slate-50 opacity-70 dark:border-slate-800 dark:bg-slate-900/50" : "",
        !soon && selected ? "border-accent ring-1 ring-accent dark:border-accent-light dark:ring-accent-light" : "",
        !soon && !selected ? "border-slate-200 hover:border-slate-400 dark:border-slate-800" : "",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{decision.title}</span>
        {soon && <Badge tone="neutral">Coming soon</Badge>}
      </div>
      <p className="mt-1 text-sm text-slate-500">{decision.description.replace(/\s*Coming soon\.?$/i, "")}</p>
    </button>
  );
}

function Choice({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-md border px-3 py-1.5 text-sm ${
        active
          ? "border-accent bg-accent-soft font-medium text-accent dark:border-accent-light dark:bg-slate-800 dark:text-accent-light"
          : "border-slate-300 text-slate-700 hover:border-slate-400 dark:border-slate-700 dark:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

function DollarInput({ value, onChange, error, placeholder }: { value: string; onChange: (v: string) => void; error?: string; placeholder?: string }) {
  return (
    <div>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-slate-500">$</span>
        <input className={`${inputClass} pl-7`} inputMode="decimal" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      </div>
      <FieldError msg={error} />
    </div>
  );
}

function FieldError({ msg }: { msg?: string }) {
  return msg ? <div className="mt-1 text-xs text-danger">{msg}</div> : null;
}
