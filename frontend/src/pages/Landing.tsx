// Landing page at "/". Static copy plus the real ProjectionChart on fixture data; "Try it" goes to /overview,
// where the existing Connect flow starts. Nothing is fetched here.
import { Link, useNavigate } from "react-router-dom";
import { useAppState } from "../state";
import { MODULE_COPY, MODULE_ORDER } from "../lib/modules";
import { LANDING_FLOOR_CENTS, LANDING_SELECTED, LANDING_SERIES } from "../lib/landingFixture";
import ProjectionChart from "../components/ProjectionChart";
import { Button } from "../components/ui";

const STEPS = [
  { label: "Understand", text: "The options that actually apply to you, with the rule and the source for each one that doesn't." },
  { label: "Check", text: "Your next twelve months under every option, the months that go tight, and an AI that tries to break your plan." },
  { label: "Act", text: "One concrete next step with a deadline, or the exact change that would turn a no into a yes." },
];

const LIMITS = [
  "Every number is computed, never generated.",
  "Every fact is cited, or the answer is ‘no source.’",
  "No carriers, no products, no investment advice.",
];

export default function Landing() {
  const navigate = useNavigate();
  const profile = useAppState((s) => s.profile);

  return (
    <div className="space-y-14 py-6 sm:py-10">
      <section className="grid items-center gap-8 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">Can I afford this? And if not, what would make it a yes?</h1>
          <p className="mt-4 text-base leading-7 text-slate-600 dark:text-slate-300">
            Waypoint reads your real income and spending, plays the decision in front of you forward twelve months, and either tells you
            you&rsquo;re clear or shows you the paths to get there.
          </p>
          <div className="mt-6">
            <Button onClick={() => navigate("/overview")}>Try it with a demo account</Button>
          </div>
        </div>
        <div className="lg:col-span-3" aria-hidden>
          <div className="pointer-events-none select-none rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-baseline justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>12-month projection, demo data</span>
              <span className="tabular">Floor $200</span>
            </div>
            <div className="mt-2">
              <ProjectionChart series={LANDING_SERIES} selectedId={LANDING_SELECTED} floorCents={LANDING_FLOOR_CENTS} height={260} />
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-xs font-medium text-slate-500 dark:text-slate-400">How it works</h2>
        <ol className="mt-3 grid gap-6 border-t border-slate-200 pt-4 dark:border-slate-800 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.label}>
              <div className="flex items-baseline gap-2">
                <span className="tabular text-xs text-slate-500 dark:text-slate-400">{i + 1}</span>
                <span className="font-medium">{s.label}</span>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-slate-200 py-3 dark:border-slate-800">
        <ul className="flex flex-col gap-1 text-sm text-slate-600 dark:text-slate-300 sm:flex-row sm:flex-wrap sm:gap-x-8">
          {LIMITS.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xs font-medium text-slate-500 dark:text-slate-400">Three decisions it handles today</h2>
        <ul className="mt-3 divide-y divide-slate-200 border-t border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {MODULE_ORDER.map((id) => (
            <li key={id}>
              <Link
                to={profile ? "/moment" : "/overview"}
                state={profile ? { moduleId: id } : undefined}
                className="flex flex-col gap-1 py-3 hover:bg-slate-50 dark:hover:bg-slate-900 sm:flex-row sm:items-baseline sm:gap-6"
              >
                <span className="w-32 shrink-0 font-medium">{MODULE_COPY[id].title}</span>
                <span className="text-sm text-slate-600 dark:text-slate-300">{MODULE_COPY[id].line}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
