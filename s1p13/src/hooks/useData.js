import { useState, useEffect, useRef } from 'react';

function validateShape(data, path) {
  if (data === null || data === undefined) throw new Error(`Empty response from ${path}`);
  if (typeof data !== 'object') throw new Error(`Expected object or array from ${path}, got ${typeof data}`);
  return data;
}

export function useData(path, options = {}) {
  const { transform, fallback = null, deps = [] } = options;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      setLoading(false);
      return undefined;
    }
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);

    fetch(path, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} loading ${path}`);
        const text = await res.text();
        if (!text || text.trim() === '') throw new Error(`Empty file at ${path}`);
        let parsed;
        try { parsed = JSON.parse(text); } catch { throw new Error(`Invalid JSON at ${path}`); }
        const validated = validateShape(parsed, path);
        return transform ? transform(validated) : validated;
      })
      .then((result) => {
        if (!controller.signal.aborted) { setData(result); setLoading(false); }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.error(`useData error [${path}]:`, err.message);
        setData(fallback);
        setError(err.message);
        setLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  return { data, loading, error };
}
