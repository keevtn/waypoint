// Stress test: "Try to break my plan" → 3 scenario cards, chart of the preferred option under each, critique panel.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { Critique, RecommendationShift, Scenario, StressResult } from "../types";
import { fmtCents, fmtMonth } from "../lib/format";
import { errorMessage } from "../lib/hooks";
import CitationChip, { CitedText } from "../components/CitationChip";
import FlagList from "../components/FlagList";
import ProjectionChart, { BASELINE_KEY, type ChartSeries } from "../components/ProjectionChart";
import { Badge, Button, Card, Empty, ErrorNote, Skeleton, SkeletonLines, type Tone } from "../components/ui";

const TEMPLATE_LABEL: Record<string, string> = {
  income_gap: "Income gap",
  shock_expense: "Unexpected expense",
  deductible_claim: "Deductible claim",
  rent_increase: "Rent increase",
  hours_cut: "Hours cut",
};

const SHIFT: Record<RecommendationShift, { label: string; tone: Tone; blurb: string }> = {
  stay: { label: "Stay with it", tone: "ok", blurb: "The case against did not find a scenario that breaks this option." },
  reconsider: { label: "Reconsider", tone: "warn", blurb: "At least one realistic scenario breaks this option. Weigh the case against before committing." },
  switch: { label: "Switch", tone: "danger", blurb: "A different option holds up better under the scenarios that matter for you." },
};

/** Human summary of scenario params; amounts are already computed by the backend. */
function describeParams(s: Scenario): string {
  const p = s.params;
  const bits: string[] = [];
  if (typeof p.amount_cents === "number") bits.push(fmtCents(p.amount_cents));
  if (typeof p.months === "number") bits.push(`${p.months} ${p.months === 1 ? "month" : "months"} without pay`);
  if (typeof p.start_month === "number") bits.push(`starting month ${p.start_month}`);
  else if (typeof p.month === "number") bits.push(`in month ${p.month}`);
  if (typeof p.pct === "number") bits.push(`${p.pct}%`);
  return bits.join(" · ");
}

export default function StressTest() {
  const navigate = useNavigate();
  const { evaluation, selectedOptionId, decisionId, stress, selectOption, setStress } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  if (!evaluation) {
    return (
      <section className="space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">Stress test</h1>
        <Empty>
          Nothing to test yet.{" "}
          <Link to="/moment" className="font-medium text-accent hover:underline dark:text-accent-light">
            Pick a decision
          </Link>{" "}
          and compare the options first.
        </Empty>
      </section>
    );
  }

  const { options, projections } = evaluation;
  const floor = useAppState.getState().profile?.safety_floor_cents ?? 20000;
  const choosable = options.filter((o) => o.status !== "disallowed");
  const preferred = options.find((o) => o.id === selectedOptionId && o.status !== "disallowed") ?? choosable[0] ?? null;

  const run = async () => {
    if (!preferred) return;
    setLoading(true);
    setError(null);
    setStress(null);
    setActiveIdx(0);
    try {
      setStress(await api.stress(decisionId, evaluation.eval_id, preferred.id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const active: StressResult | null = stress?.scenarios[activeIdx] ?? null;
  const scenarioResult = active && preferred ? (active.results[preferred.id] ?? null) : null;
  const scenarioBaseline = active?.results[BASELINE_KEY] ?? null;
  const shownScenario = scenarioResult ?? scenarioBaseline;
  const shownLabel = scenarioResult
    ? `${preferred?.label} · under scenario`
    : scenarioBaseline
      ? "Baseline · under scenario"
      : null;

  const series: ChartSeries[] = [];
  if (projections[BASELINE_KEY]) series.push({ id: BASELINE_KEY, label: "Baseline (no policy)", result: projections[BASELINE_KEY] });
  if (preferred && projections[preferred.id]) series.push({ id: preferred.id, label: `${preferred.label} · as planned`, result: projections[preferred.id] });
  if (shownScenario && shownLabel) series.push({ id: "scenario", label: shownLabel, result: shownScenario });

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Try to break my plan</h1>
          <p className="text-sm text-slate-500">
            The AI picks three scenarios tailored to your cash flow. The projection engine runs them; the AI then argues against your pick.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/compare">
            <Button variant="secondary">Back to compare</Button>
          </Link>
          <Button onClick={() => navigate("/action")} disabled={!preferred}>
            Choose and get the action card
          </Button>
        </div>
      </header>

      <Card title="Your pick to test">
        <div className="flex flex-wrap items-center gap-2">
          {choosable.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => selectOption(o.id)}
              aria-pressed={preferred?.id === o.id}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                preferred?.id === o.id
                  ? "border-accent bg-accent-soft font-medium text-accent dark:border-accent-light dark:bg-slate-800 dark:text-accent-light"
                  : "border-slate-300 text-slate-700 hover:border-slate-400 dark:border-slate-700 dark:text-slate-200"
              }`}
            >
              {o.label}
              <span className="tabular ml-2 text-xs text-slate-500">{fmtCents(o.price.cents)}/mo</span>
            </button>
          ))}
          <div className="ml-auto">
            <Button onClick={run} disabled={loading || !preferred}>
              {loading ? "Running scenarios…" : stress ? "Run again" : "Try to break my plan"}
            </Button>
          </div>
        </div>
        {stress && preferred && stress.critique.preferred_option_id !== preferred.id && (
          <p className="mt-2 text-xs text-warn">These results were run for a different pick. Run again to test {preferred.label}.</p>
        )}
      </Card>

      {error && <ErrorNote message={error} />}

      {loading && (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Card key={i}>
                <Skeleton className="mb-2 h-4 w-1/2" />
                <SkeletonLines n={3} />
              </Card>
            ))}
          </div>
          <Card title="Projection under scenario">
            <Skeleton className="h-[280px]" />
          </Card>
          <Card title="The case against your pick">
            <SkeletonLines n={4} />
          </Card>
        </>
      )}

      {stress && !loading && (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            {stress.scenarios.map((s, i) => {
              const r = preferred ? (s.results[preferred.id] ?? s.results[BASELINE_KEY]) : s.results[BASELINE_KEY];
              const tone: Tone = !r ? "neutral" : r.months_negative.length > 0 ? "danger" : r.months_below_floor.length > 0 ? "warn" : "ok";
              const on = i === activeIdx;
              return (
                <button
                  key={`${s.scenario.template_id}-${i}`}
                  type="button"
                  onClick={() => setActiveIdx(i)}
                  aria-pressed={on}
                  className={`rounded-lg border p-4 text-left transition ${
                    on ? "border-accent ring-1 ring-accent dark:border-accent-light dark:ring-accent-light" : "border-slate-200 hover:border-slate-400 dark:border-slate-800"
                  } bg-white dark:bg-slate-900`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm font-semibold">{TEMPLATE_LABEL[s.scenario.template_id] ?? s.scenario.template_id}</div>
                    <Badge tone={tone}>{tone === "danger" ? "Goes negative" : tone === "warn" ? "Below floor" : tone === "ok" ? "Holds" : "No run"}</Badge>
                  </div>
                  <div className="tabular mt-0.5 text-xs text-slate-500">{describeParams(s.scenario)}</div>
                  <p className="mt-2 text-sm leading-5 text-slate-700 dark:text-slate-300">{s.scenario.rationale}</p>
                  {r && (
                    <div className="tabular mt-2 text-xs text-slate-500">
                      Lowest point <span className="font-medium text-slate-700 dark:text-slate-200">{fmtCents(r.min_balance_cents)}</span>
                      {r.min_balance_date && <> in {fmtMonth(r.min_balance_date.slice(0, 7))}</>}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <Card
              title={active ? `Projection · ${TEMPLATE_LABEL[active.scenario.template_id] ?? active.scenario.template_id}` : "Projection"}
              aside={
                shownScenario && (
                  <span className="text-xs text-slate-500">
                    Lowest point{" "}
                    <span className={`tabular font-medium ${shownScenario.min_balance_cents < 0 ? "text-danger" : shownScenario.min_balance_cents < floor ? "text-warn" : "text-ok"}`}>
                      {fmtCents(shownScenario.min_balance_cents)}
                    </span>
                  </span>
                )
              }
            >
              {series.length > 0 ? (
                <ProjectionChart series={series} selectedId="scenario" floorCents={floor} height={280} />
              ) : (
                <Empty>No projection returned for this scenario.</Empty>
              )}
              {!scenarioResult && scenarioBaseline && (
                <p className="mt-2 text-xs text-slate-500">This scenario was only run against the baseline; the option line shows the plan without the shock.</p>
              )}
            </Card>
            <Card title="Flags under this scenario">
              {shownScenario ? <FlagList flags={shownScenario.flags} /> : <Empty>No flags.</Empty>}
            </Card>
          </div>

          <CritiquePanel critique={stress.critique} optionLabel={options.find((o) => o.id === stress.critique.preferred_option_id)?.label ?? stress.critique.preferred_option_id} />
        </>
      )}

      {!stress && !loading && !error && (
        <Empty>Pick the option you are leaning toward above, then let the AI try to break it.</Empty>
      )}
    </section>
  );
}

function CritiquePanel({ critique, optionLabel }: { critique: Critique; optionLabel: string }) {
  const v = SHIFT[critique.recommendation_shift];
  return (
    <Card
      title={`The case against ${optionLabel}`}
      aside={
        <Badge tone={v.tone} className="px-2 py-1 text-xs">
          Verdict: {v.label}
        </Badge>
      }
    >
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">{v.blurb}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-danger">Case against</h3>
          <ul className="space-y-1.5 text-sm">
            {critique.case_against.map((p, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-danger" />
                <span>
                  <CitedText text={p} citations={critique.citations} />
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-ok">Case for</h3>
          <ul className="space-y-1.5 text-sm">
            {critique.case_for.map((p, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ok" />
                <span>
                  <CitedText text={p} citations={critique.citations} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {critique.citations.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3 text-xs text-slate-500 dark:border-slate-800">
          <span>Sources:</span>
          {critique.citations.map((c, i) => (
            <CitationChip key={c.chunk_id} citation={c} index={i + 1} />
          ))}
        </div>
      )}
    </Card>
  );
}
