"use client";
import { useEffect, useState } from "react";
import { readApi } from "./client";
import type { ApiResult } from "./contracts";

export function useReadResource<T>(path: string) {
  const [revision, setRevision] = useState(0);
  const [settled, setSettled] = useState<{
    key: string;
    result: ApiResult<T>;
  } | null>(null);
  const key = `${revision}:${path}`;
  useEffect(() => {
    const controller = new AbortController();
    readApi<T>(path, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setSettled({ key, result });
      })
      .catch(() => {
        /* Aborted requests never replace newer results. */
      });
    return () => controller.abort();
  }, [path, key]);
  return {
    result: settled?.key === key ? settled.result : null,
    refresh: () => setRevision((value) => value + 1),
  };
}
