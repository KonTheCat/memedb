"use client";

import { useEffect, useState } from "react";
import { imageUrl } from "./api";
import { getStoredPassword } from "./auth";

export function useAuthedImage(id: string): string | null {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset while the new image loads
    setSrc(null);

    fetch(imageUrl(id), { headers: { "X-App-Password": getStoredPassword() ?? "" } })
      .then((res) => (res.ok ? res.blob() : Promise.reject(res)))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  return src;
}
