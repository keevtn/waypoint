// Product link lookup for the Big purchase form. POST /products/lookup; on high or low confidence the
// parent prefills name and price (still editable); on none the note shows inline. Never blocks the form.
import { useState } from "react";
import { api } from "../api";
import type { ProductLookupResponse } from "../types";
import { errorMessage } from "../lib/hooks";
import { Button, Field, inputClass } from "./ui";

export default function ProductLookup({ onFound }: { onFound: (r: ProductLookupResponse) => void }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductLookupResponse | null>(null);

  const lookup = async () => {
    const u = url.trim();
    if (!/^https?:\/\/\S+$/i.test(u)) {
      setError("Paste a full link starting with http:// or https://.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.productLookup(u);
      setResult(r);
      if (r.confidence !== "none") onFound(r);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const domain = (() => {
    try {
      return new URL(result?.source_url || url.trim()).hostname.replace(/^www\./, "");
    } catch {
      return null;
    }
  })();

  return (
    <div>
      <Field label="Product link" hint="Optional. Paste a product page to fill in the name and price.">
        <div className="flex gap-2">
          <input
            className={inputClass}
            type="url"
            inputMode="url"
            placeholder="https://"
            value={url}
            aria-label="Product link"
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void lookup();
              }
            }}
          />
          <Button type="button" variant="secondary" onClick={() => void lookup()} disabled={busy} className="shrink-0">
            {busy ? "Looking up…" : "Look up"}
          </Button>
        </div>
      </Field>
      {error && <div className="mt-1 text-xs text-danger">{error}</div>}
      {result && result.confidence === "none" && (
        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{result.note ?? "No product details found at that link. Enter the name and price below."}</div>
      )}
      {result && result.confidence !== "none" && (
        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          {result.image_url && <img src={result.image_url} alt="" className="h-10 w-10 rounded border border-slate-200 object-cover dark:border-slate-800" />}
          <span>
            {result.confidence === "low" ? "Best guess from " : "From "}
            {domain ?? "the page"}. Check the name and price before you continue.
          </span>
        </div>
      )}
    </div>
  );
}
