// Compare: option cards (left), projection chart + flags (right), explanation panel, Ask-with-sources.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { Flag } from "../types";
import { fmtCents, fmtDollars } from "../lib/format";
import { errorMessage, useDarkMode } from "../lib/hooks";
import AskWithSources from "../components/AskWithSources";
import ExplanationPanel, { ExplanationSkeleton, TightMonthPanel } from "../components/ExplanationPanel";
import FlagList from "../components/FlagList";
import OptionCard from "../components/OptionCard";
import ProjectionChart, { BASELINE_KEY, seriesColor } from "../components/ProjectionChart";
import { Button, Card, Empty, ErrorNote } from "../components/ui";

export default function Compare() {
  const { profile, evaluation, explanations, selectedOptionId, decisionId, inputs, selectOption, setExplanations } = useAppState();
  const dark = useDarkMode();
  const [explainError, setExplainError] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [activeMonth, setActiveMonth] = useState<string | null>(null);

  const evalId = evaluation?.eval_id ?? null;

  // Explanations are an LLM call: load after the chart renders, never block on it.
  useEffect(() => {
    if (!evalId || explanations !== null) return;
    let alive = true;
    setExplainLoading(true);
    setExplainError(null);
    api
      .explain(decisionId, evalId)
      .then((r) => alive && setExplanations(r.explanations))
      .catch((e: unknown) => alive && setExplainError(errorMessage(e)))
      .finally(() => alive && setExplainLoading(false));
    return () => {
      alive = false;
    };
  }, [evalId, explanations, decisionId, setExplanations]);

  if (!evaluation) {
    return (
      <section className="space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">Compare options</h1>
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
    ...(projections[BASELINE_KEY] ? [{ id: BASELINE_KEY, label: "Baseline (no policy)", result: projections[BASELINE_KEY] }] : []),
    ...options.filter((o) => projections[o.id]).map((o) => ({ id: o.id, label: o.label, result: projections[o.id] })),
  ];
  const colorFor = (optionId: string) => seriesColor(options.findIndex((o) => o.id === optionId), dark);

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Compare options</h1>
          {inputs && (
            <p className="text-xs text-slate-500">
              {fmtDollars(inputs.vehicle_value_cents)} car · {inputs.financed ? `financed, ${fmtCents(inputs.loan_payment_cents ?? 0)}/mo` : "owned outright"} · age{" "}
              <span className="tabular">{inputs.driver_age}</span> · comfortable with a {fmtDollars(inputs.deductible_comfort_cents)} deductible
            </p>
          )}
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
          <p className="px-1 text-xs text-slate-500">
            Prices marked Estimate come from a cited public source, not a carrier. Get real quotes before you decide.
          </p>
        </div>

        <div className="space-y-4">
          <Card
            title="12-month projection"
            aside={
              selectedProjection && (
                <span className="text-xs text-slate-500">
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

      {selected &&
        (explainLoading && explanations === null ? (
          <ExplanationSkeleton />
        ) : explainError ? (
          <Card title="Why this option">
            <ErrorNote message={`Could not load the explanation: ${explainError}`} />
            <div className="mt-2">
              <Button variant="secondary" onClick={() => setExplanations(null)}>
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
