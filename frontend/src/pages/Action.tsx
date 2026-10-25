// Action card: printable next steps for the chosen option. "Talk to a human" hidden without a URL.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppState } from "../state";
import type { ActionCard } from "../types";
import { fmtCents, fmtDate } from "../lib/format";
import { friendlyError } from "../lib/hooks";
import CitationChip, { CitedText } from "../components/CitationChip";
import { describeAttributes, PriceBadge } from "../components/OptionCard";
import { Button, Empty, ErrorNote, Skeleton, SkeletonLines } from "../components/ui";

const inflight = new Map<string, Promise<ActionCard>>();

export default function Action() {
  const { evaluation, selectedOptionId, decisionId, actionCard, evalGen, selectOption, setActionCard, withFreshEval } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const options = evaluation?.options ?? [];
  const choosable = options.filter((o) => o.status !== "disallowed");
  const option = options.find((o) => o.id === selectedOptionId && o.status !== "disallowed") ?? choosable[0] ?? null;
  const evalId = evaluation?.eval_id ?? null;
  const optionId = option?.id ?? null;

  useEffect(() => {
    if (!evalId || !optionId || (actionCard && actionCard.option_id === optionId)) return;
    let alive = true;
    setLoading(true);
    setError(null);
    // Share one in-flight request per (eval, option): StrictMode remounts and quick re-renders must not
    // trigger a second 10-20s LLM call.
    const key = `${evalGen}:${optionId}`;
    const req =
      inflight.get(key) ?? withFreshEval((id) => api.action(decisionId, id, optionId)).finally(() => inflight.delete(key));
    inflight.set(key, req);
    req
      .then((c) => alive && setActionCard(c))
      .catch((e: unknown) => alive && setError(friendlyError(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [evalId, evalGen, optionId, decisionId, actionCard, setActionCard, withFreshEval]);

  if (!evaluation || !option) {
    return (
      <section className="space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">Action card</h1>
        <Empty>
          No option chosen yet.{" "}
          <Link to={evaluation ? "/compare" : "/moment"} className="font-medium text-accent hover:underline dark:text-accent-light">
            {evaluation ? "Compare the options" : "Pick a decision"}
          </Link>{" "}
          first.
        </Empty>
      </section>
    );
  }

  const card = actionCard && actionCard.option_id === option.id ? actionCard : null;

  const copyText = async () => {
    if (!card) return;
    try {
      await navigator.clipboard.writeText(asText(card, option.label));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2 print:hidden">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Your next action</h1>
          <p className="text-sm text-slate-500">A coverage configuration, not a carrier. Take this to real people and get real quotes.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {choosable.length > 1 && (
            <select
              aria-label="Chosen option"
              className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              value={option.id}
              onChange={(e) => selectOption(e.target.value)}
            >
              {choosable.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
          <Button variant="secondary" onClick={copyText} disabled={!card}>
            {copied ? "Copied" : "Copy as text"}
          </Button>
          <Button variant="secondary" onClick={() => window.print()} disabled={!card}>
            Print
          </Button>
          {card?.deadline && (
            <Button variant="secondary" onClick={() => downloadIcs(card, option.label)}>
              Add reminder
            </Button>
          )}
        </div>
      </header>

      <article className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm print:border-0 print:shadow-none dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Chosen configuration</div>
            <div className="mt-1 text-lg font-semibold">{option.label}</div>
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300">
              {describeAttributes(option.attributes).map((r) => (
                <div key={r.label} className="flex gap-1">
                  <dt className="text-slate-500">{r.label}</dt>
                  <dd className="tabular font-medium">{r.value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="text-right">
            <div className="tabular text-xl font-semibold">{fmtCents(option.price.cents)}</div>
            <div className="text-xs text-slate-500">per month</div>
            <div className="mt-1 flex justify-end">
              <PriceBadge price={option.price} />
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4">
            <ErrorNote message={`Could not build the action card: ${error}`} />
            <div className="mt-2">
              <Button variant="secondary" onClick={() => setActionCard(null)}>
                Retry
              </Button>
            </div>
          </div>
        )}

        {!card && !error && (
          <div className="mt-5 space-y-5" aria-busy>
            <Skeleton className="h-6 w-3/4" />
            <SkeletonLines n={5} />
            <SkeletonLines n={3} />
            <p className="text-xs text-slate-400">Writing your action card{loading ? "…" : ""}</p>
          </div>
        )}

        {card && (
          <>
            <h2 className="mt-5 text-xl font-semibold leading-snug tracking-tight">
              <CitedText text={card.headline} citations={card.citations} />
            </h2>

            {card.deadline && (
              <div className="mt-3 inline-flex items-baseline gap-2 rounded-md border border-warn/40 bg-amber-50 px-3 py-1.5 text-sm dark:bg-amber-950/40">
                <span className="text-xs font-medium uppercase tracking-wide text-warn">Deadline</span>
                <span className="tabular font-semibold">{fmtDate(card.deadline)}</span>
                {card.deadline_reason && <span className="text-xs text-slate-600 dark:text-slate-300">{card.deadline_reason}</span>}
              </div>
            )}

            <section className="mt-6">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Next steps</h3>
              <ol className="space-y-2">
                {card.steps.map((s, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-6">
                    <span className="tabular flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent dark:bg-slate-800 dark:text-accent-light">
                      {i + 1}
                    </span>
                    <span>
                      <CitedText text={s} citations={card.citations} />
                    </span>
                  </li>
                ))}
              </ol>
            </section>

            {card.questions_to_ask.length > 0 && (
              <section className="mt-6">
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Questions to ask an agent</h3>
                <ul className="space-y-1.5">
                  {card.questions_to_ask.map((q, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-6">
                      <span aria-hidden className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                      <span>
                        <CitedText text={q} citations={card.citations} />
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {card.talk_to_human_url && (
              <section className="mt-6 rounded-md border border-slate-200 p-4 dark:border-slate-800 print:hidden">
                <div className="text-sm font-medium">Talk to a human</div>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                  An independent agent or your own bank can check this configuration against your lender&apos;s letter before you buy.
                </p>
                <a
                  href={card.talk_to_human_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-block text-sm font-medium text-accent hover:underline dark:text-accent-light"
                >
                  Open contact options
                </a>
              </section>
            )}

            {card.citations.length > 0 && (
              <section className="mt-6 border-t border-slate-100 pt-3 dark:border-slate-800">
                <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Sources</h3>
                <ol className="space-y-1 text-xs">
                  {card.citations.map((c, i) => (
                    <li key={c.chunk_id} className="flex items-start gap-2">
                      <CitationChip citation={c} index={i + 1} />
                      <span className="text-slate-600 dark:text-slate-300">
                        {c.title}
                        {c.year ? ` (${c.year})` : ""} · <span className="break-all">{c.url}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </>
        )}
        <p className="mt-6 text-[11px] text-slate-400">
          Estimates and educational information, not financial advice. Premiums shown are estimates until you enter a quote.
        </p>
      </article>

      <div className="flex justify-between print:hidden">
        <Link to="/stress" className="text-sm text-slate-500 hover:underline">
          Back to stress test
        </Link>
        <Link to="/" className="text-sm text-slate-500 hover:underline">
          Start over
        </Link>
      </div>
    </section>
  );
}

const stripMarkers = (s: string) => s.replace(/\s?\[(s|c):[^\]]+\]/g, "");

function asText(card: ActionCard, optionLabel: string): string {
  const lines = [
    `${optionLabel}`,
    stripMarkers(card.headline),
    "",
    "Next steps:",
    ...card.steps.map((s, i) => `${i + 1}. ${stripMarkers(s)}`),
  ];
  if (card.questions_to_ask.length) lines.push("", "Questions to ask:", ...card.questions_to_ask.map((q) => `- ${stripMarkers(q)}`));
  if (card.deadline) lines.push("", `Deadline: ${fmtDate(card.deadline)}${card.deadline_reason ? ` (${card.deadline_reason})` : ""}`);
  if (card.citations.length) lines.push("", "Sources:", ...card.citations.map((c, i) => `[${i + 1}] ${c.title}, ${c.publisher}. ${c.url}`));
  lines.push("", "Estimates and educational information, not financial advice.");
  return lines.join("\n");
}

function downloadIcs(card: ActionCard, optionLabel: string) {
  if (!card.deadline) return;
  const d = card.deadline.replace(/-/g, "");
  const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Waypoint//Action card//EN",
    "BEGIN:VEVENT",
    `UID:waypoint-${card.option_id}-${d}@local`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${d}`,
    `SUMMARY:${esc(`Insurance deadline: ${optionLabel}`)}`,
    `DESCRIPTION:${esc(asText(card, optionLabel))}`,
    "BEGIN:VALARM",
    "TRIGGER:-P3D",
    "ACTION:DISPLAY",
    `DESCRIPTION:${esc(stripMarkers(card.headline))}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "waypoint-reminder.ics";
  a.click();
  URL.revokeObjectURL(url);
}
