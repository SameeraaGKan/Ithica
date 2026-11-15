"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DataSource, Sourced } from "./types";

// Fetch now, then every `ms`. Keeps the last good data if a poll fails.
export function usePoll<T>(fetcher: () => Promise<Sourced<T>>, ms: number) {
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<DataSource>("mock");
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  const live = useRef(false);
  const busy = useRef(false);
  const refresh = useCallback(async () => {
    if (busy.current) return; // a slow poll still running: don't stack another (out-of-order answers)
    busy.current = true;
    try {
      const res = await fetchRef.current();
      // once live data has arrived, a slow/failed poll's mock fallback must not replace it (coins jumped around)
      if (res.source !== "live" && live.current) return;
      live.current = res.source === "live";
      setData(res.data);
      setSource(res.source);
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, ms);
    return () => clearInterval(id);
  }, [refresh, ms]);

  return { data, source, refresh };
}
