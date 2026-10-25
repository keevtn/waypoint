// Compare: option cards (left), projection chart + flags (right), explanation panel, Ask-with-sources.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAppState } from "../state";
import { applySuggestionPatch, baselineLabel, fmtApr, isAutoInputs, isBigPurchaseInputs, isRentInputs, priceFootnote, type DecisionInputs } from "../lib/decisionInputs";
import SuggestionsPanel from "../components/SuggestionsPanel";
import type { Suggestion } from "../types";
import { api } from "../api";
import type { Flag } from "../types";
import { fmtCents, fmtDate, fmtDollars } from "../lib/format";
import { friendlyError, useDarkMode } from "../lib/hooks";
import AskWithSources from "../components/AskWithSources";
import ExplanationPanel, { ExplanationSkeleton, TightMonthPanel } from "../components/ExplanationPanel";
import FlagList from "../components/FlagList";
import OptionCard from "../components/OptionCard";
import ProjectionChart, { BASELINE_KEY, seriesColor } from "../components/ProjectionChart";
import { Button, Card, Empty, ErrorNote } from "../components/ui";

export default function Compare() {
  const { profile, evaluation, explanations, explainStatus, explainError, selectedOptionId, decisionId, inputs, selectOption, prefetchExplanations } =
    useAppState();
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);
  // The suggestion the user tapped, with the list it came from, so the panel can keep showing it as "Applied"
  // after the re-evaluation (which usually no longer needs to suggest anything).
  const [applied, setApplied] = useState<{ id: string; evalId: string; suggestions: Suggestion[] } | null>(null);

  /** Merge a suggestion's patch into the inputs and re-run /evaluate; the new options replace the current ones. */
  const applySuggestion = async (s: Suggestion) => {
    if (!inputs || applyingId) return;
    const next = applySuggestionPatch(inputs, s);
    const from = evaluation?.suggestions ?? [];
    setApplyingId(s.id);
    setApplyError(null);
    try {
      const result = await api.evaluate(next.decisionId, next.inputs);
      setApplied({ id: s.id, evalId: result.eval_id, suggestions: from });
      const st = useAppState.getState();
      st.setInputs(next);
      st.setEvaluation(result);
      // Land on the option the suggestion was computed for, when it exists in the new evaluation.
      if (result.options.some((o) => o.id === s.projected.option_id)) st.selectOption(s.projected.option_id);
      st.prefetchExplanations();
      setActiveMonth(null);
    } catch (e) {
      setApplyError(friendlyError(e));
    } finally {
      setApplyingId(null);
    }
  };
  const dark = useDarkMode();
  const [activeMonth, setActiveMonth] = useState<string | null>(null);

  const evalId = evaluation?.eval_id ?? null;
  const explainLoading = explainStatus === "loading";

  // Explanations are an LLM call (10-20s live). Moment already prefetched them; this covers a direct landing or a retry.
  useEffect(() => {
    if (evalId && explainStatus === "idle") prefetchExplanations();
  }, [evalId, explainStatus, prefetchExplanations]);

  if (!evaluation) {
    return (
      <section className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">Compare options</h1>
        <Empty>
          Nothing to compare yet.{" "}
          <Link to="/moment" className="font-medium text-accent hover:underline dark:text-accent-light">
            Pick a decision
          </Link>{" "}
          and we will run each option through your projection.
        </Empty>
      </section>
    );
  }

  const floor = profile?.safety_floor_cents ?? 20000;
  const { options, constraints, projections } = evaluation;
  const selected = options.find((o) => o.id === selectedOptionId) ?? null;
  const selectedProjection = selected ? projections[selected.id] : undefined;
  const explanation = selected && explanations ? (explanations.find((e) => e.option_id === selected.id) ?? null) : null;
  const activeFlag: Flag | null =
    activeMonth && selectedProjection ? (selectedProjection.flags.find((f) => f.month === activeMonth) ?? null) : null;

  const series = [
    ...(projections[BASELINE_KEY] ? [{ id: BASELINE_KEY, label: baselineLabel(decisionId), result: projections[BASELINE_KEY] }] : []),
    ...options.filter((o) => projections[o.id]).map((o) => ({ id: o.id, label: o.label, result: projections[o.id] })),
  ];
  const colorFor = (optionId: string) => seriesColor(options.findIndex((o) => o.id === optionId), dark);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Compare options</h1>
          {inputs && <p className="text-xs text-slate-500 dark:text-slate-400">{inputsSummary(inputs)}</p>}
        </div>
        <div className="flex gap-2">
          <Link to="/moment">
            <Button variant="secondary">Edit inputs</Button>
          </Link>
          <Link to="/stress">
            <Button disabled={!selected || selected.status === "disallowed"}>Stress test this pick</Button>
          </Link>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-3">
          {options.map((o) => (
            <OptionCard
              key={o.id}
              option={o}
              constraints={constraints}
              projection={projections[o.id]}
              floorCents={floor}
              selected={o.id === selectedOptionId}
              color={colorFor(o.id)}
              onSelect={() => {
                selectOption(o.id);
                setActiveMonth(null);
              }}
            />
          ))}
          <p className="px-1 text-xs text-slate-500 dark:text-slate-400">
            {priceFootnote(decisionId)}
          </p>
        </div>

        <div className="space-y-4">
          <Card
            title="12-month projection"
            aside={
              selectedProjection && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {selected?.label}: lowest point{" "}
                  <span className={`tabular font-medium ${selectedProjection.min_balance_cents < 0 ? "text-danger" : selectedProjection.min_balance_cents < floor ? "text-warn" : "text-ok"}`}>
                    {fmtCents(selectedProjection.min_balance_cents)}
                  </span>
                </span>
              )
            }
          >
            <ProjectionChart series={series} selectedId={selectedOptionId} floorCents={floor} height={300} onMonthClick={setActiveMonth} />
          </Card>

          <Card title={selected ? `Flags · ${selected.label}` : "Flags"}>
            {selectedProjection ? (
              <FlagList flags={selectedProjection.flags} activeMonth={activeMonth} onSelect={(f) => setActiveMonth(f.month)} />
            ) : (
              <Empty>Select an option to see its flags.</Empty>
            )}
          </Card>

          {activeMonth && (
            <TightMonthPanel month={activeMonth} explanation={explanation} flag={activeFlag} loading={explainLoading} onClose={() => setActiveMonth(null)} />
          )}
        </div>
      </div>

      {applyError && <ErrorNote message={applyError} />}
      <SuggestionsPanel
        suggestions={applied && applied.evalId === evaluation.eval_id ? applied.suggestions : (evaluation.suggestions ?? [])}
        options={options}
        floorCents={floor}
        applyingId={applyingId}
        appliedId={applied && applied.evalId === evaluation.eval_id ? applied.id : null}
        onApply={applySuggestion}
      />

      {selected &&
        (explainLoading && explanations === null ? (
          <ExplanationSkeleton />
        ) : explainStatus === "error" ? (
          <Card title="Why this option">
            <ErrorNote message={explainError ?? "Could not load the explanation."} />
            <div className="mt-2">
              <Button variant="secondary" onClick={() => useAppState.setState({ explainStatus: "idle", explainError: null })}>
                Retry
              </Button>
            </div>
          </Card>
        ) : (
          <ExplanationPanel explanation={explanation} constraints={constraints} optionLabel={selected.label} />
        ))}

      <AskWithSources module={decisionId} />
    </section>
  );
}

/** One-line recap of what the user told us, per module. */
function inputsSummary(d: DecisionInputs): string {
  if (isAutoInputs(d)) {
    const i = d.inputs;
    return `${fmtDollars(i.vehicle_value_cents)} car · ${i.financed ? `financed, ${fmtCents(i.loan_payment_cents ?? 0)}/mo` : "owned outright"} · age ${i.driver_age} · comfortable with a ${fmtDollars(i.deductible_comfort_cents)} deductible`;
  }
  if (isRentInputs(d)) {
    const i = d.inputs;
    const current = i.current_rent_cents === null ? "current rent from your transactions" : i.current_rent_cents === 0 ? "no rent today" : `paying ${fmtCents(i.current_rent_cents)}/mo now`;
    return `${i.units.length} units · ${current} · each option is "move to this unit", the baseline is staying put`;
  }
  if (isBigPurchaseInputs(d)) {
    const i = d.inputs;
    const fin = i.financing
      ? `your offer: ${fmtApr(i.financing.apr_bps)} APR over ${i.financing.term_months} months${i.financing.down_payment_cents > 0 ? `, ${fmtCents(i.financing.down_payment_cents)} down` : ""}`
      : "no lender offer yet, so financed plans use an assumed APR";
    return `${i.name} · ${fmtCents(i.amount_cents)} on ${fmtDate(i.date)} · ${fin}`;
  }
  return "";
}
