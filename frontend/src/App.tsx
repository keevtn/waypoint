import { NavLink, Route, Routes } from "react-router-dom";
import Overview from "./pages/Overview";
import Moment from "./pages/Moment";
import Compare from "./pages/Compare";
import StressTest from "./pages/StressTest";
import Action from "./pages/Action";

// Top stepper echoes the track's chain: Understand → Compare → Stress test → Act.
const STEPS = [
  { to: "/", label: "Understand" },
  { to: "/compare", label: "Compare" },
  { to: "/stress", label: "Stress test" },
  { to: "/action", label: "Act" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-6">
          <span className="font-semibold text-accent dark:text-accent-light">Waypoint</span>
          <nav className="flex gap-4 text-sm">
            {STEPS.map((s) => (
              <NavLink
                key={s.to}
                to={s.to}
                end={s.to === "/"}
                className={({ isActive }) =>
                  isActive ? "text-accent dark:text-accent-light font-medium" : "text-slate-500"
                }
              >
                {s.label}
              </NavLink>
            ))}
          </nav>
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
      <footer className="border-t border-slate-200 dark:border-slate-800 px-4 py-3 text-xs text-slate-500 text-center">
        Estimates and educational information, not financial advice. Numbers are computed from your
        transactions; facts are cited.
      </footer>
    </div>
  );
}
