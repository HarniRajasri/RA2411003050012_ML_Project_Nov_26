import { useCallback, useEffect, useRef, useState } from "react";

/** Loads data on mount / when deps change. `refreshMs` polls. Returns { data, error, loading, reload }. */
export function useFetch(loader, deps = [], refreshMs = 0) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async (quiet = false) => {
    const id = ++seq.current;
    if (!quiet) setLoading(true);
    try {
      const d = await loaderRef.current();
      if (id === seq.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(e);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    run();
    if (!refreshMs) return undefined;
    const t = setInterval(() => run(true), refreshMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refreshMs]);

  return { data, error, loading, reload: () => run(true) };
}
