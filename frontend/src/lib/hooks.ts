import { useEffect, useState } from "react";

export interface Async<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Run an async fn once per dep change; never throws. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], enabled = true): Async<T> {
  const [state, setState] = useState<Async<T>>({ data: null, error: null, loading: enabled });
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then(
      (data) => alive && setState({ data, error: null, loading: false }),
      (e: unknown) => alive && setState({ data: null, error: errorMessage(e), loading: false }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export const errorMessage = (e: unknown): string => (e instanceof Error ? e.message : String(e));

const darkQuery = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

/** True when the OS prefers dark mode; tracks changes. */
export function useDarkMode(): boolean {
  const [dark, setDark] = useState(darkQuery?.matches ?? false);
  useEffect(() => {
    if (!darkQuery) return;
    const onChange = (e: MediaQueryListEvent) => setDark(e.matches);
    darkQuery.addEventListener("change", onChange);
    return () => darkQuery.removeEventListener("change", onChange);
  }, []);
  return dark;
}
