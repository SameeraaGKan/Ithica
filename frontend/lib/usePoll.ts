"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DataSource, Sourced } from "./types";

// Fetch now, then every `ms`. Keeps the last good data if a poll fails.
export function usePoll<T>(fetcher: () => Promise<Sourced<T>>, ms: number) {
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<DataSource>("mock");
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  const refresh = useCallback(async () => {
    const res = await fetchRef.current();
    setData(res.data);
    setSource(res.source);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, ms);
    return () => clearInterval(id);
  }, [refresh, ms]);

  return { data, source, refresh };
}
