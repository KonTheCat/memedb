"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useMsal } from "@azure/msal-react";
import { imageUrl, listMemes, searchImage, searchText, type MemeResponse, type SearchResultItem } from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import { bucketLabel } from "@/lib/display";
import { buildCsv, mergeRows, parseCsv, slugifyQuery, type CalibrationRow } from "@/lib/calibrationCsv";
import styles from "./page.module.css";

const STORAGE_KEY = "memedb-calibration-labels";
type Mode = "text" | "image";

export default function CalibratePage() {
  const { accounts } = useMsal();
  const admin = accounts.length > 0 && isAdmin(accounts[0]);

  const [mode, setMode] = useState<Mode>("text");
  const [textQuery, setTextQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null);
  const [activeQueryText, setActiveQueryText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [labels, setLabels] = useState<CalibrationRow[]>([]);
  const [hydrated, setHydrated] = useState(false);

  const [browseMemes, setBrowseMemes] = useState<MemeResponse[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load any in-progress session on mount - real calibration work, not a
  // disposable draft, so a reload shouldn't lose it. The durable unit is
  // still the exported CSV (import/export below); this is just same-tab
  // crash protection.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load on mount
      if (raw) setLabels(JSON.parse(raw));
    } catch {
      // private browsing / cleared storage - start empty, still usable this session
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(labels));
    } catch {
      // storage unavailable - labels still work for this session, just won't persist
    }
  }, [labels, hydrated]);

  useEffect(() => {
    if (mode !== "image" || !admin) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load the meme picker when switching to image mode
    setBrowseLoading(true);
    listMemes(null, 24, 0)
      .then(setBrowseMemes)
      .catch(() => setBrowseMemes([]))
      .finally(() => setBrowseLoading(false));
  }, [mode, admin]);

  if (!admin) {
    return (
      <main className={styles.main}>
        <h1 className={styles.title}>Search calibration</h1>
        <p className={styles.message}>
          {accounts.length === 0 ? "Sign in as an admin to use this tool." : "Admins only."}
        </p>
      </main>
    );
  }

  async function runTextQuery(e: React.FormEvent) {
    e.preventDefault();
    const q = textQuery.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    try {
      const { results } = await searchText(q, null, 10);
      setResults(results);
      setActiveQueryId(slugifyQuery(q));
      setActiveQueryText(q);
    } catch {
      setError("Search failed.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  // Image-mode queries are always a corpus meme, never a raw upload: an
  // uploaded file has no stable reference the calibration script could
  // re-fetch later, while a meme_id does (see scripts/calibrate_thresholds.py).
  async function runImageQuery(meme: MemeResponse) {
    setLoading(true);
    setError(null);
    try {
      const blob = await fetch(imageUrl(meme.id)).then((res) => res.blob());
      const file = new File([blob], `${meme.id}.jpg`, { type: blob.type || "image/jpeg" });
      const { results } = await searchImage(file, null, 10);
      setResults(results);
      setActiveQueryId(meme.id);
      setActiveQueryText(meme.id);
    } catch {
      setError("Search failed.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function setLabel(result: SearchResultItem, rank: number, label: 0 | 1 | 2) {
    if (!activeQueryId) return;
    const row: CalibrationRow = {
      queryId: activeQueryId,
      query: activeQueryText,
      rank,
      memeId: result.id,
      caption: result.caption,
      templateName: result.templateName,
      cosine: result.similarity,
      label,
    };
    setLabels((prev) => mergeRows(prev, [row]));
  }

  function currentLabel(memeId: string): number | undefined {
    return labels.find((row) => row.queryId === activeQueryId && row.memeId === memeId)?.label;
  }

  function handleExport() {
    const csv = buildCsv(labels);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${mode}_labels.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      setLabels((prev) => mergeRows(prev, parseCsv(text)));
    });
    e.target.value = "";
  }

  function handleClear() {
    if (!window.confirm("Clear all labeled rows in this session? This cannot be undone.")) return;
    setLabels([]);
  }

  function handleModeChange(next: Mode) {
    setMode(next);
    setResults([]);
    setActiveQueryId(null);
    setError(null);
  }

  return (
    <main className={styles.main}>
      <h1 className={styles.title}>Search calibration</h1>
      <p className={styles.subtitle}>
        Score each result 0 (unrelated) / 1 (loosely relevant) / 2 (strongly relevant) to calibrate the thresholds in
        memedb/relevance.py. See scripts/CALIBRATION_README.md for the full rubric.
      </p>

      <div className={styles.toggle}>
        <button className={mode === "text" ? styles.activeTab : styles.tab} onClick={() => handleModeChange("text")}>
          Text query
        </button>
        <button
          className={mode === "image" ? styles.activeTab : styles.tab}
          onClick={() => handleModeChange("image")}
        >
          Image query
        </button>
      </div>

      {mode === "text" ? (
        <form className={styles.queryForm} onSubmit={runTextQuery}>
          <input
            className={styles.input}
            type="text"
            placeholder="Query text"
            value={textQuery}
            onChange={(e) => setTextQuery(e.target.value)}
          />
          <button className={styles.submit} type="submit" disabled={loading}>
            Run
          </button>
        </form>
      ) : (
        <div className={styles.browse}>
          <p className={styles.browseHint}>Pick an existing meme to use as the query image:</p>
          {browseLoading ? (
            <p className={styles.message}>Loading…</p>
          ) : (
            <div className={styles.browseGrid}>
              {browseMemes.map((meme) => (
                <button
                  key={meme.id}
                  type="button"
                  className={activeQueryId === meme.id ? styles.browseItemActive : styles.browseItem}
                  onClick={() => runImageQuery(meme)}
                >
                  <Image src={imageUrl(meme.id)} alt={meme.templateName || "meme"} fill sizes="120px" unoptimized />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <p className={styles.errorMessage}>{error}</p>}
      {loading && <p className={styles.message}>Searching…</p>}

      {activeQueryId && results.length > 0 && (
        <div className={styles.results}>
          {results.map((result, i) => {
            const rank = i + 1;
            const selected = currentLabel(result.id);
            return (
              <div key={result.id} className={styles.card}>
                <div className={styles.cardImage}>
                  <Image
                    src={imageUrl(result.id)}
                    alt={result.templateName || "meme"}
                    fill
                    sizes="140px"
                    unoptimized
                  />
                </div>
                <div className={styles.cardBody}>
                  <span className={styles.cardTemplate}>{result.templateName || "Untitled"}</span>
                  <span className={styles.cardMeta}>
                    {bucketLabel(result.bucket)} · cosine {result.similarity.toFixed(3)}
                  </span>
                  <p className={styles.cardCaption}>{result.caption}</p>
                  <div className={styles.scoreRow}>
                    {([0, 1, 2] as const).map((score) => (
                      <button
                        key={score}
                        type="button"
                        className={selected === score ? styles.scoreButtonActive : styles.scoreButton}
                        onClick={() => setLabel(result, rank, score)}
                      >
                        {score}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className={styles.sessionBar}>
        <span className={styles.sessionCount}>{labels.length} labeled rows this session</span>
        <button type="button" onClick={handleExport} disabled={labels.length === 0}>
          Export CSV
        </button>
        <button type="button" onClick={() => fileInputRef.current?.click()}>
          Import CSV
        </button>
        <input ref={fileInputRef} type="file" accept=".csv" hidden onChange={handleImport} />
        <button type="button" onClick={handleClear} disabled={labels.length === 0}>
          Clear session
        </button>
      </div>
    </main>
  );
}
