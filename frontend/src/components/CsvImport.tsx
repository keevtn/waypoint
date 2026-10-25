// CSV import panel on Overview: an alternative to Connect. The file is posted once as multipart to
// /bank/import_csv; warnings come back inline; on success the profile and baseline load exactly as Connect does.
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAppState } from "../state";
import { dollarsToCents } from "../lib/format";
import { errorMessage } from "../lib/hooks";
import { markConnected } from "../lib/session";
import { Button, Field, inputClass } from "./ui";

export default function CsvImport({ onImported }: { onImported?: (institution: string | null) => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [balance, setBalance] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [warnings, setWarnings] = useState<string[]>([]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) {
      setFieldError("Choose a CSV file.");
      return;
    }
    const cents = balance.trim() === "" ? null : dollarsToCents(balance);
    if (balance.trim() !== "" && (cents === null || cents < 0)) {
      setFieldError("Enter a dollar amount of 0 or more, or leave it blank.");
      return;
    }
    setFieldError(undefined);
    setBusy(true);
    setError(null);
    setWarnings([]);
    try {
      const r = await api.importCsv(file, cents);
      setWarnings(r.warnings);
      markConnected();
      const st = useAppState.getState();
      const [p, b] = await Promise.all([api.profile(), api.baseline(st.horizonMonths)]);
      st.setProfile(p);
      st.setBaseline(b);
      if (st.evaluation) st.setEvaluation(null);
      onImported?.(r.institution);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <Button variant="secondary" type="button" onClick={() => setOpen(true)}>
        Import a CSV instead
      </Button>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="mt-4 max-w-md rounded-md bg-slate-50 p-4 dark:bg-slate-950/60">
      <div className="text-sm font-medium">Import a CSV</div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Your file is read once to build your profile and is never stored.</p>
      <div className="mt-3 space-y-3">
        <Field label="Transactions CSV">
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="Transactions CSV"
            className="block w-full text-sm text-slate-700 file:mr-3 file:rounded file:border file:border-slate-300 file:bg-transparent file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-800 dark:text-slate-200 dark:file:border-slate-700 dark:file:text-slate-100"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
        <Field label="Current balance" hint="Optional. Blank uses the balance in the file, if any.">
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-slate-500 dark:text-slate-400">$</span>
            <input className={`${inputClass} pl-7`} inputMode="decimal" value={balance} aria-label="Current balance in dollars" onChange={(e) => setBalance(e.target.value)} />
          </div>
        </Field>
        {fieldError && <div className="text-xs text-danger">{fieldError}</div>}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Importing…" : "Import"}
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </Button>
      </div>
      {error && <div className="mt-2 text-xs text-danger">{error}</div>}
      {warnings.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-slate-500 dark:text-slate-400">
          {warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </form>
  );
}
