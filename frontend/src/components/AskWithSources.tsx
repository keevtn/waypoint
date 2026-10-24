// "Ask with sources": answers corpus questions with citations; refusals render as a neutral grey box, never an error.
import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { RagAskResponse } from "../types";
import { errorMessage } from "../lib/hooks";
import CitationChip, { CitedText } from "./CitationChip";
import { Button, Card, ErrorNote, SkeletonLines, inputClass } from "./ui";

const SUGGESTIONS = ["What does limited tort mean in Pennsylvania?", "Should I invest my emergency fund in index funds?"];

export default function AskWithSources({ module }: { module: string | null }) {
  const [q, setQ] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [result, setResult] = useState<RagAskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (question: string) => {
    const t = question.trim();
    if (!t) return;
    setAsked(t);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.ask(t, module));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(q);
  };

  return (
    <Card title="Ask with sources" aside={<span className="text-xs text-slate-400">Answers only from cited public sources</span>}>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          className={inputClass}
          placeholder="Ask about coverage terms, state requirements, or lender rules"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Question"
        />
        <Button type="submit" disabled={loading || !q.trim()}>
          Ask
        </Button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQ(s);
              void ask(s);
            }}
            className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:text-slate-300"
          >
            {s}
          </button>
        ))}
      </div>

      {asked && (
        <div className="mt-4">
          <div className="mb-1.5 text-xs text-slate-500">You asked: {asked}</div>
          {loading && (
            <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
              <SkeletonLines n={2} />
            </div>
          )}
          {error && <ErrorNote message={error} />}
          {result && result.refusal && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
              <div className="mb-0.5 text-xs font-medium uppercase tracking-wide text-slate-500">Not answered</div>
              {result.refusal}
            </div>
          )}
          {result && result.answer && (
            <div className="rounded-md border border-slate-200 p-3 text-sm leading-6 dark:border-slate-800">
              <CitedText text={result.answer} citations={result.citations} />
              {result.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800">
                  <span>Sources:</span>
                  {result.citations.map((c, i) => (
                    <CitationChip key={c.chunk_id} citation={c} index={i + 1} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
