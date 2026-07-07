"use client";

import { useState } from "react";
import { ApiError, ingestMeme } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import styles from "./UploadPanel.module.css";

export default function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<string>(CATEGORIES[0]);
  const [templateName, setTemplateName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await ingestMeme(file, category, templateName, sourceUrl);
      setMessage({ kind: "success", text: `Uploaded — id ${result.id}` });
      setFile(null);
      setTemplateName("");
      setSourceUrl("");
      onUploaded();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const detail = err.detail as { id?: string } | string;
        const existingId = typeof detail === "object" ? detail.id : undefined;
        setMessage({ kind: "error", text: `Duplicate image — already stored as ${existingId ?? "unknown id"}` });
      } else if (err instanceof ApiError) {
        setMessage({ kind: "error", text: String(err.detail) });
      } else {
        setMessage({ kind: "error", text: "Upload failed." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <button className={styles.toggle} onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} Upload a meme
      </button>
      {open && (
        <form className={styles.form} onSubmit={handleSubmit}>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Template name (optional)"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Source URL (optional)"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
          />
          <button type="submit" disabled={!file || submitting}>
            {submitting ? "Uploading…" : "Upload"}
          </button>
          {message && (
            <p className={message.kind === "success" ? styles.success : styles.errorMessage}>{message.text}</p>
          )}
        </form>
      )}
    </div>
  );
}
