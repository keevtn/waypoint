import { useEffect } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { USE_FIXTURES, api } from "./api";
import { hasConnected } from "./lib/session";
import { useAppState } from "./state";
import Overview from "./pages/Overview";
import Moment from "./pages/Moment";
import Compare from "./pages/Compare";
import StressTest from "./pages/StressTest";
import Action from "./pages/Action";

// Top stepper echoes the track's chain: Understand → Compare → Stress test → Act.
const STEPS: { to: string; label: string; match: string[] }[] = [
  { to: "/", label: "Understand", match: ["/"] },
  { to: "/compare", label: "Compare", match: ["/moment", "/compare"] },
  { to: "/stress", label: "Stress test", match: ["/stress"] },
  { to: "/action", label: "Act", match: ["/action"] },
];

export default function App() {
  const { pathname } = useLocation();
  const { profile, evaluation, setProfile, setBaseline } = useAppState();

  // Silently restore a profile after a refresh, but only if this browser already went through Connect:
  // the demo must start at the Connect step, and the local backend serves a profile before any connect.
  useEffect(() => {
    if (profile || USE_FIXTURES || !hasConnected()) return;
    let alive = true;
    api
      .profile()
      .then(async (p) => {
        if (!alive) return;
        setProfile(p);
        try {
          setBaseline(await api.baseline());
        } catch {
          /* chart stays in its loading state */
        }
      })
      .catch(() => {
        /* not connected yet: Overview shows the connect button */
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stepIndex = STEPS.findIndex((s) => s.match.includes(pathname));
  const reached = (i: number) => (i <= 1 ? true : !!evaluation);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="font-semibold tracking-tight text-accent dark:text-accent-light">
            Waypoint
          </NavLink>
          <nav aria-label="Steps" className="flex items-center gap-1 text-sm">
            {STEPS.map((s, i) => {
              const active = i === stepIndex;
              const done = i < stepIndex;
              const enabled = reached(i);
              return (
                <NavLink
                  key={s.to}
                  to={enabled ? s.to : "#"}
                  aria-current={active ? "step" : undefined}
                  aria-disabled={!enabled}
                  onClick={(e) => !enabled && e.preventDefault()}
                  className={[
                    "flex items-center gap-1.5 rounded px-2 py-1",
                    active ? "font-medium text-accent dark:text-accent-light" : done ? "text-slate-700 dark:text-slate-200" : "text-slate-400",
                    enabled ? "hover:bg-slate-100 dark:hover:bg-slate-800" : "cursor-default",
                  ].join(" ")}
                >
                  <span className="tabular text-[11px]">{i + 1}</span>
                  <span className="hidden sm:inline">{s.label}</span>
                  {i < STEPS.length - 1 && <span aria-hidden className="ml-2 h-3 w-px bg-slate-300 dark:bg-slate-700" />}
                </NavLink>
              );
            })}
          </nav>
          {profile && (
            <span className="ml-auto hidden text-xs text-slate-500 dark:text-slate-400 md:inline">
              Demo bank · Plaid sandbox
            </span>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/moment" element={<Moment />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/stress" element={<StressTest />} />
          <Route path="/action" element={<Action />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 dark:border-slate-800">
        <div className="mx-auto max-w-6xl px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
          Estimates and educational information, not financial advice. Numbers are computed from your transactions; facts are cited.
        </div>
      </footer>
    </div>
  );
}
