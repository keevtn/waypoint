// Moment: module picker + hand-built auto insurance form (no generic schema renderer).
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { AutoInsuranceInputs, BigPurchaseInputs, DecisionSummary, UserQuote } from "../types";
import { DEFAULT_MODULE, MODULE_COPY, isModuleId, orderModules } from "../lib/modules";
import { isAutoInputs, isBigPurchaseInputs, isRentInputs, type DecisionInputs, type RentInputs, type RentUnit } from "../lib/decisionInputs";
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


// ---------- Rent module (mirrors backend/app/decisions/rent/inputs.py) ----------

interface UnitForm {
  label: string;
  rent: string;
  deposit: string;
  utilities: string;
  leaseMonths: string;
  startDate: string;
}

interface RentFormState {
  units: UnitForm[];
  /** "" = use the rent detected in transactions. */
  currentRent: string;
}

const MIN_UNITS = 2;
const MAX_UNITS = 4;

/** First day of the month after next: a realistic lease start for someone looking now. */
const nextLeaseStart = (asOf: string): string => {
  const [y, m] = asOf.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1 + 2, 1)).toISOString().slice(0, 10);
};

const emptyUnit = (startDate: string): UnitForm => ({ label: "", rent: "", deposit: "", utilities: "", leaseMonths: "12", startDate });

// Demo defaults: three State College units around the $850 the persona pays now; one fits, one is flagged, one is over 45%.
const rentDefaultsFor = (asOf: string): RentFormState => {
  const start = nextLeaseStart(asOf);
  return {
    currentRent: "",
    units: [
      { label: "Room in a shared house", rent: "520", deposit: "520", utilities: "40", leaseMonths: "12", startDate: start },
      { label: "Shared 2BR near campus", rent: "725", deposit: "725", utilities: "60", leaseMonths: "12", startDate: start },
      { label: "Studio downtown", rent: "1050", deposit: "1050", utilities: "90", leaseMonths: "12", startDate: start },
    ],
  };
};

const rentFromInputs = (i: RentInputs): RentFormState => ({
  currentRent: centsToDollarsText(i.current_rent_cents),
  units: i.units.map((u) => ({
    label: u.label,
    rent: centsToDollarsText(u.rent_cents),
    deposit: centsToDollarsText(u.deposit_cents),
    utilities: centsToDollarsText(u.utilities_est_cents),
    leaseMonths: String(u.lease_months),
    startDate: u.start_date,
  })),
});


// ---------- Big purchase module (mirrors backend/app/decisions/big_purchase/inputs.py) ----------

interface PurchaseFormState {
  name: string;
  amount: string;
  date: string;
  hasOffer: boolean;
  aprPct: string; // "24.99"
  termMonths: string;
  downPayment: string;
}

// Demo default: the $1,800 laptop next week, no lender offer (so the financed plans use the assumed APR).
const purchaseDefaultsFor = (asOf: string): PurchaseFormState => ({
  name: "Laptop",
  amount: "1800",
  date: addDays(asOf, 7),
  hasOffer: false,
  aprPct: "",
  termMonths: "12",
  downPayment: "",
});

const purchaseFromInputs = (i: BigPurchaseInputs): PurchaseFormState => ({
  name: i.name,
  amount: centsToDollarsText(i.amount_cents),
  date: i.date,
  hasOffer: i.financing !== null,
  aprPct: i.financing ? String(i.financing.apr_bps / 100) : "",
  termMonths: i.financing ? String(i.financing.term_months) : "12",
  downPayment: i.financing ? centsToDollarsText(i.financing.down_payment_cents) : "",
});

/** "24.99" -> 2499 basis points; null when not a number. */
const pctToBps = (s: string): number | null => {
  const t = s.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  return Math.round(Number(t) * 100);
};

export default function Moment() {
  const navigate = useNavigate();
  const location = useLocation();
  const { profile, inputs, decisionId, setInputs, setEvaluation } = useAppState();
  const decisions = useAsync(() => api.decisions(), []);
  // Preselection: a module handed over by the landing page, else the module behind the last evaluation, else the first in product order.
  const requested = (location.state as { moduleId?: unknown } | null)?.moduleId;
  const [moduleId, setModuleId] = useState<string>(isModuleId(requested) ? requested : inputs ? decisionId : DEFAULT_MODULE);
  const asOf = profile?.as_of ?? todayIso();
  const [form, setForm] = useState<FormState>(() => (isAutoInputs(inputs) ? fromInputs(inputs.inputs) : defaultsFor(asOf)));
  const [rentForm, setRentForm] = useState<RentFormState>(() => (isRentInputs(inputs) ? rentFromInputs(inputs.inputs) : rentDefaultsFor(asOf)));
  const [purchase, setPurchase] = useState<PurchaseFormState>(() => (isBigPurchaseInputs(inputs) ? purchaseFromInputs(inputs.inputs) : purchaseDefaultsFor(asOf)));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // If the profile arrives after first render, refresh the deadline default once.
  useEffect(() => {
    if (profile && !inputs) {
      setForm((f) => ({ ...f, registrationDeadline: addDays(profile.as_of, 30) }));
      const start = nextLeaseStart(profile.as_of);
      setRentForm((f) => ({ ...f, units: f.units.map((u) => ({ ...u, startDate: start })) }));
      setPurchase((f) => ({ ...f, date: addDays(profile.as_of, 7) }));
    }
  }, [profile, inputs]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const detectedRent = profile?.recurring.find((r) => /rent/i.test(r.label));
  const currentRentHint = detectedRent
    ? `Optional. Blank uses the ${fmtCents(Math.abs(detectedRent.amount_cents))}/mo rent in your transactions. Enter 0 if you pay no rent today.`
    : "Optional. Blank uses the rent detected in your transactions; enter 0 if you pay no rent today.";

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


  const setUnit = (i: number, patch: Partial<UnitForm>) =>
    setRentForm((f) => ({ ...f, units: f.units.map((u, j) => (j === i ? { ...u, ...patch } : u)) }));
  const addUnit = () => setRentForm((f) => (f.units.length >= MAX_UNITS ? f : { ...f, units: [...f.units, emptyUnit(nextLeaseStart(asOf))] }));
  const removeUnit = (i: number) => setRentForm((f) => (f.units.length <= MIN_UNITS ? f : { ...f, units: f.units.filter((_, j) => j !== i) }));

  const validateRent = (): RentInputs | null => {
    const e: Record<string, string> = {};
    const units: RentUnit[] = [];
    rentForm.units.forEach((u, i) => {
      const rent = dollarsToCents(u.rent);
      const deposit = u.deposit.trim() === "" ? 0 : dollarsToCents(u.deposit);
      const utilities = u.utilities.trim() === "" ? 0 : dollarsToCents(u.utilities);
      const months = Number(u.leaseMonths);
      if (!u.label.trim()) e[`unit${i}.label`] = "Give this unit a name.";
      if (rent === null || rent <= 0) e[`unit${i}.rent`] = "Enter the monthly rent.";
      if (deposit === null || deposit < 0) e[`unit${i}.deposit`] = "Enter an amount or leave blank.";
      if (utilities === null || utilities < 0) e[`unit${i}.utilities`] = "Enter an amount or leave blank.";
      if (!Number.isInteger(months) || months < 1 || months > 36) e[`unit${i}.leaseMonths`] = "1 to 36 months.";
      if (!/^\d{4}-\d{2}-\d{2}$/.test(u.startDate)) e[`unit${i}.startDate`] = "Pick a start date.";
      if (rent !== null && deposit !== null && utilities !== null)
        units.push({
          label: u.label.trim(),
          rent_cents: rent,
          deposit_cents: deposit,
          utilities_est_cents: utilities,
          lease_months: months,
          start_date: u.startDate,
        });
    });
    const labels = rentForm.units.map((u) => u.label.trim().toLowerCase());
    labels.forEach((l, i) => {
      if (l && labels.indexOf(l) !== i) e[`unit${i}.label`] = "Two units have the same name.";
    });
    const current = rentForm.currentRent.trim() === "" ? null : dollarsToCents(rentForm.currentRent);
    if (rentForm.currentRent.trim() !== "" && (current === null || current < 0)) e.currentRent = "Enter an amount or leave blank.";
    setErrors(e);
    if (Object.keys(e).length > 0 || units.length < MIN_UNITS) return null;
    return { units, current_rent_cents: current };
  };


  const setP = <K extends keyof PurchaseFormState>(k: K, v: PurchaseFormState[K]) => setPurchase((f) => ({ ...f, [k]: v }));

  const validatePurchase = (): BigPurchaseInputs | null => {
    const e: Record<string, string> = {};
    const amount = dollarsToCents(purchase.amount);
    const name = purchase.name.trim();
    if (!name) e.pName = "Say what you're buying.";
    if (name.length > 60) e.pName = "Keep the name under 60 characters.";
    if (amount === null || amount <= 0) e.pAmount = "Enter the full price.";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(purchase.date)) e.pDate = "Pick a date.";
    let financing: BigPurchaseInputs["financing"] = null;
    if (purchase.hasOffer) {
      const bps = pctToBps(purchase.aprPct);
      const term = Number(purchase.termMonths);
      const down = purchase.downPayment.trim() === "" ? 0 : dollarsToCents(purchase.downPayment);
      if (bps === null || bps > 10000) e.pApr = "Enter the APR as a percentage, e.g. 24.99.";
      if (!Number.isInteger(term) || term < 1 || term > 84) e.pTerm = "1 to 84 monthly payments.";
      if (down === null || down < 0) e.pDown = "Enter an amount or leave blank.";
      if (down !== null && amount !== null && down >= amount) e.pDown = "A down payment that large means you're paying cash.";
      if (bps !== null && down !== null) financing = { apr_bps: bps, term_months: term, down_payment_cents: down };
    }
    setErrors(e);
    if (Object.keys(e).length > 0) return null;
    return { name, amount_cents: amount as number, date: purchase.date, financing };
  };

  const onSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    let tagged: DecisionInputs | null = null;
    if (moduleId === "rent") {
      const parsed = validateRent();
      if (parsed) tagged = { decisionId: "rent", inputs: parsed };
    } else if (moduleId === "big_purchase") {
      const parsed = validatePurchase();
      if (parsed) tagged = { decisionId: "big_purchase", inputs: parsed };
    } else {
      const parsed = validate();
      if (parsed) tagged = { decisionId: "auto_insurance", inputs: parsed };
    }
    if (!tagged) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      setInputs(tagged);
      const result = await api.evaluate(tagged.decisionId, tagged.inputs, useAppState.getState().horizonMonths);
      setEvaluation(result);
      // /explain takes 10-20s live: start it now so Compare has it by the time the user clicks an option.
      useAppState.getState().prefetchExplanations();
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
        <h1 className="text-2xl font-semibold tracking-tight">What are you deciding?</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Each option is run through your projection; tight months are flagged.</p>
      </header>

      {!profile && (
        <div className="rounded-md border border-warn/40 bg-amber-50 px-3 py-2 text-sm text-warn dark:bg-amber-950/40 dark:text-amber-300">
          Connect your bank first.{" "}
          <Link to="/overview" className="font-medium underline">
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
        {decisions.data && orderModules(decisions.data).map((d) => (
          <ModuleCard key={d.id} decision={d} selected={moduleId === d.id} onSelect={() => {
              setModuleId(d.id);
              setErrors({});
              setSubmitError(null);
            }} />
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
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Lenders set coverage requirements for a financed car.</p>
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
              <Field label="Deductible you could pay on short notice" hint="What you could cover next month without borrowing.">
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
                <p className="text-xs text-slate-500 dark:text-slate-400">Optional. A quote replaces the estimate for that configuration.</p>
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
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Pennsylvania rules apply. {profile && <>Floor {fmtCents(profile.safety_floor_cents)}.</>}
              </span>
              <Button type="submit" disabled={submitting || !profile}>
                {submitting ? "Running projections…" : "Compare options"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {moduleId === "rent" && (
        <Card title="Rent · the units you're weighing">
          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Staying put is the baseline. Each unit is tested as a move, with the deposit and first month due at lease start.
            </p>

            <ul className="space-y-4">
              {rentForm.units.map((u, i) => (
                <li key={i} className="rounded-md bg-slate-50 p-4 dark:bg-slate-950/60">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Unit {i + 1}</span>
                    {rentForm.units.length > MIN_UNITS && (
                      <Button type="button" variant="ghost" onClick={() => removeUnit(i)} className="px-2 py-1 text-xs">
                        Remove
                      </Button>
                    )}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Name" hint="How you refer to it.">
                      <input className={inputClass} placeholder="e.g. Studio on Beaver Ave" value={u.label} onChange={(e) => setUnit(i, { label: e.target.value })} />
                      <FieldError msg={errors[`unit${i}.label`]} />
                    </Field>
                    <Field label="Monthly rent">
                      <DollarInput value={u.rent} onChange={(v) => setUnit(i, { rent: v })} error={errors[`unit${i}.rent`]} />
                    </Field>
                    <Field label="Security deposit" hint="Due at signing. Blank = none.">
                      <DollarInput value={u.deposit} onChange={(v) => setUnit(i, { deposit: v })} error={errors[`unit${i}.deposit`]} />
                    </Field>
                    <Field label="Utilities not included" hint="Monthly estimate. Blank = none.">
                      <DollarInput value={u.utilities} onChange={(v) => setUnit(i, { utilities: v })} error={errors[`unit${i}.utilities`]} />
                    </Field>
                    <Field label="Lease length (months)">
                      <input className={inputClass} inputMode="numeric" value={u.leaseMonths} onChange={(e) => setUnit(i, { leaseMonths: e.target.value })} />
                      <FieldError msg={errors[`unit${i}.leaseMonths`]} />
                    </Field>
                    <Field label="Lease start" hint="Deposit and first month are due then.">
                      <input type="date" className={inputClass} value={u.startDate} onChange={(e) => setUnit(i, { startDate: e.target.value })} />
                      <FieldError msg={errors[`unit${i}.startDate`]} />
                    </Field>
                  </div>
                </li>
              ))}
            </ul>

            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={addUnit}
                disabled={rentForm.units.length >= MAX_UNITS}
                className="text-xs font-medium text-accent hover:underline disabled:cursor-not-allowed disabled:opacity-50 dark:text-accent-light"
              >
                Add another unit
              </button>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {rentForm.units.length} of {MAX_UNITS}
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="What you pay now" hint={currentRentHint}>
                <DollarInput
                  value={rentForm.currentRent}
                  onChange={(v) => setRentForm((f) => ({ ...f, currentRent: v }))}
                  error={errors.currentRent}
                  placeholder="from your transactions"
                />
              </Field>
            </div>

            {submitError && <ErrorNote message={submitError} />}

            <div className="flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                HUD 30% standard. {profile && <>Floor {fmtCents(profile.safety_floor_cents)}.</>}
              </span>
              <Button type="submit" disabled={submitting || !profile}>
                {submitting ? "Running projections…" : "Compare units"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {moduleId === "big_purchase" && (
        <Card title="Big purchase · what, how much, and when">
          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Cash on that date is tested against financing. If neither keeps your floor, a date or a plan that does is suggested.
            </p>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="What are you buying?">
                <input className={inputClass} placeholder="e.g. Laptop" value={purchase.name} onChange={(e) => setP("name", e.target.value)} />
                <FieldError msg={errors.pName} />
              </Field>
              <Field label="Full price">
                <DollarInput value={purchase.amount} onChange={(v) => setP("amount", v)} error={errors.pAmount} />
              </Field>
              <Field label="When" hint="Purchase date, or when payments would start.">
                <input type="date" className={inputClass} value={purchase.date} onChange={(e) => setP("date", e.target.value)} />
                <FieldError msg={errors.pDate} />
              </Field>
            </div>

            <fieldset>
              <legend className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-200">Do you have a financing offer?</legend>
              <div className="flex gap-2">
                <Choice active={!purchase.hasOffer} onClick={() => setP("hasOffer", false)}>
                  Not yet
                </Choice>
                <Choice active={purchase.hasOffer} onClick={() => setP("hasOffer", true)}>
                  Yes, I know the terms
                </Choice>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {purchase.hasOffer
                  ? "Financed plans use your lender's numbers."
                  : "Without an offer, financed plans use an assumed APR and are marked Estimate."}
              </p>
            </fieldset>

            {purchase.hasOffer && (
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="APR (%)" hint="As printed on the offer, e.g. 24.99. Zero is fine.">
                  <input className={inputClass} inputMode="decimal" value={purchase.aprPct} onChange={(e) => setP("aprPct", e.target.value)} />
                  <FieldError msg={errors.pApr} />
                </Field>
                <Field label="Number of monthly payments">
                  <input className={inputClass} inputMode="numeric" value={purchase.termMonths} onChange={(e) => setP("termMonths", e.target.value)} />
                  <FieldError msg={errors.pTerm} />
                </Field>
                <Field label="Down payment" hint="Paid on the purchase date. Blank = none.">
                  <DollarInput value={purchase.downPayment} onChange={(v) => setP("downPayment", v)} error={errors.pDown} />
                </Field>
              </div>
            )}

            {submitError && <ErrorNote message={submitError} />}

            <div className="flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
              <span className="text-xs text-slate-500 dark:text-slate-400">{profile && <>Floor {fmtCents(profile.safety_floor_cents)}.</>}</span>
              <Button type="submit" disabled={submitting || !profile}>
                {submitting ? "Running projections…" : "Compare ways to pay"}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </section>
  );
}

const SUPPORTED = new Set(["auto_insurance", "rent", "big_purchase"]);

function ModuleCard({ decision, selected, onSelect }: { decision: DecisionSummary; selected: boolean; onSelect: () => void }) {
  const soon = !SUPPORTED.has(decision.id);
  return (
    <button
      type="button"
      disabled={soon}
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "rounded-md border p-5 text-left",
        soon ? "cursor-not-allowed border-slate-200 bg-slate-50 opacity-70 dark:border-slate-800 dark:bg-slate-900/50" : "",
        !soon && selected ? "border-accent bg-white ring-1 ring-inset ring-accent dark:border-accent-light dark:bg-slate-900 dark:ring-accent-light" : "",
        !soon && !selected ? "border-slate-200 bg-white hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900" : "",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{isModuleId(decision.id) ? MODULE_COPY[decision.id].title : decision.title}</span>
        {soon && <Badge tone="neutral">Coming soon</Badge>}
      </div>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {isModuleId(decision.id) ? MODULE_COPY[decision.id].line : decision.description.replace(/\s*Coming soon\.?$/i, "")}
      </p>
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
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-slate-500 dark:text-slate-400">$</span>
        <input className={`${inputClass} pl-7`} inputMode="decimal" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      </div>
      <FieldError msg={error} />
    </div>
  );
}

function FieldError({ msg }: { msg?: string }) {
  return msg ? <div className="mt-1 text-xs text-danger">{msg}</div> : null;
}
