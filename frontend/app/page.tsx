"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import CategoryFilter from "@/components/CategoryFilter";
import LogoutButton from "@/components/LogoutButton";
import SearchBar, { SearchMode } from "@/components/SearchBar";
import ResultsGrid from "@/components/ResultsGrid";
import UploadPanel from "@/components/UploadPanel";
import { loginRequest } from "@/lib/msalConfig";
import { ApiError, countMemes, deleteMeme, listMemes, searchImage, searchText } from "@/lib/api";
import { fromMemeResponse, fromSearchResult, type DisplayMeme } from "@/lib/display";
import styles from "./page.module.css";

const PAGE_SIZE = 24;

type ActiveSearch = { kind: "browse" } | { kind: "text"; query: string } | { kind: "image"; file: File };

export default function Home() {
  const { instance } = useMsal();
  const [category, setCategory] = useState<string | null>(null);
  const [mode, setMode] = useState<SearchMode>("text");
  const [active, setActive] = useState<ActiveSearch>({ kind: "browse" });
  const [memes, setMemes] = useState<DisplayMeme[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState<number | null>(null);

  const runSearch = useCallback(async (search: ActiveSearch, cat: string | null, pageNum: number) => {
    setLoading(true);
    setError(null);
    try {
      if (search.kind === "browse") {
        const [docs, count] = await Promise.all([listMemes(cat, PAGE_SIZE, pageNum * PAGE_SIZE), countMemes(cat)]);
        setMemes(docs.map(fromMemeResponse));
        setTotalPages(Math.max(1, Math.ceil(count / PAGE_SIZE)));
      } else if (search.kind === "text") {
        const results = await searchText(search.query, cat);
        setMemes(results.map(fromSearchResult));
        setTotalPages(null);
      } else {
        const results = await searchImage(search.file, cat);
        setMemes(results.map(fromSearchResult));
        setTotalPages(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Something went wrong.");
      setMemes([]);
      setTotalPages(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load on mount
    runSearch(active, category, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleCategorySelect(cat: string | null) {
    setCategory(cat);
    setPage(0);
    runSearch(active, cat, 0);
  }

  function handleTextSearch(query: string) {
    const next: ActiveSearch = { kind: "text", query };
    setActive(next);
    setPage(0);
    runSearch(next, category, 0);
  }

  function handleImageSearch(file: File) {
    const next: ActiveSearch = { kind: "image", file };
    setActive(next);
    setPage(0);
    runSearch(next, category, 0);
  }

  function handleModeChange(nextMode: SearchMode) {
    setMode(nextMode);
    if (nextMode === "text" && active.kind === "image") {
      const next: ActiveSearch = { kind: "browse" };
      setActive(next);
      setPage(0);
      runSearch(next, category, 0);
    }
  }

  function handleUploaded() {
    const next: ActiveSearch = { kind: "browse" };
    setActive(next);
    setMode("text");
    setPage(0);
    runSearch(next, category, 0);
  }

  function handlePrevPage() {
    const prevPage = Math.max(0, page - 1);
    setPage(prevPage);
    runSearch(active, category, prevPage);
  }

  function handleNextPage() {
    const nextPage = page + 1;
    setPage(nextPage);
    runSearch(active, category, nextPage);
  }

  async function handleDelete(id: string) {
    try {
      await deleteMeme(id);
      setMemes((prev) => prev.filter((meme) => meme.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to delete meme.");
    }
  }

  return (
    <main className={styles.main}>
      <AuthenticatedTemplate>
        <LogoutButton />
      </AuthenticatedTemplate>
      <h1 className={styles.title}>MemeDB</h1>

      <div className={styles.uploadSection}>
        <AuthenticatedTemplate>
          <UploadPanel onUploaded={handleUploaded} />
        </AuthenticatedTemplate>
        <UnauthenticatedTemplate>
          <button type="button" onClick={() => instance.loginRedirect(loginRequest)}>
            Sign in to upload
          </button>
        </UnauthenticatedTemplate>
      </div>

      <SearchBar
        mode={mode}
        onModeChange={handleModeChange}
        onTextSearch={handleTextSearch}
        onImageSearch={handleImageSearch}
      />

      <CategoryFilter selected={category} onSelect={handleCategorySelect} />

      <ResultsGrid memes={memes} loading={loading} error={error} onDelete={handleDelete} />

      {active.kind === "browse" && totalPages !== null && (
        <div className={styles.pagination}>
          <button type="button" onClick={handlePrevPage} disabled={page === 0 || loading}>
            ← Prev
          </button>
          <span className={styles.pageNumber}>
            Page {page + 1} of {totalPages}
          </span>
          <button type="button" onClick={handleNextPage} disabled={page + 1 >= totalPages || loading}>
            Next →
          </button>
        </div>
      )}
    </main>
  );
}
