"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { ApiError, deleteMeme, getMeme, updateMeme, type MemeResponse } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { useAuthedImage } from "@/lib/useAuthedImage";
import LogoutButton from "@/components/LogoutButton";
import styles from "./page.module.css";

export default function MemeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [meme, setMeme] = useState<MemeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [category, setCategory] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [caption, setCaption] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const imageSrc = useAuthedImage(id);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load meme data on mount / id change
    setLoading(true);
    setError(null);
    getMeme(id)
      .then((doc) => {
        if (cancelled) return;
        setMeme(doc);
        setCategory(doc.category);
        setTemplateName(doc.templateName);
        setCaption(doc.caption);
        setOcrText(doc.ocrText);
        setTagsInput(doc.tags.join(", "));
        setSourceUrl(doc.sourceUrl);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? String(err.detail) : "Failed to load meme.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveMessage(null);
    try {
      const updated = await updateMeme(id, {
        category,
        templateName,
        caption,
        ocrText,
        tags: tagsInput
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        sourceUrl,
      });
      setMeme(updated);
      setSaveMessage({ kind: "success", text: "Saved." });
    } catch (err) {
      setSaveMessage({
        kind: "error",
        text: err instanceof ApiError ? String(err.detail) : "Failed to save changes.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this meme? This cannot be undone.")) return;
    try {
      await deleteMeme(id);
      router.push("/");
    } catch (err) {
      setSaveMessage({
        kind: "error",
        text: err instanceof ApiError ? String(err.detail) : "Failed to delete meme.",
      });
    }
  }

  if (loading) return <p className={styles.message}>Loading…</p>;
  if (error || !meme) return <p className={styles.error}>{error ?? "Meme not found."}</p>;

  return (
    <main className={styles.main}>
      <LogoutButton />
      <Link href="/" className={styles.back}>
        ← Back
      </Link>

      <div className={styles.imageWrapper}>
        {imageSrc && (
          <Image
            src={imageSrc}
            alt={meme.templateName || meme.caption || "meme"}
            fill
            sizes="(max-width: 700px) 100vw, 700px"
            className={styles.image}
            unoptimized
          />
        )}
      </div>

      <form className={styles.form} onSubmit={handleSave}>
        <label className={styles.field}>
          <span>Template name</span>
          <input type="text" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
        </label>

        <label className={styles.field}>
          <span>Category</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span>Caption</span>
          <textarea rows={2} value={caption} onChange={(e) => setCaption(e.target.value)} />
        </label>

        <label className={styles.field}>
          <span>OCR text</span>
          <textarea rows={3} value={ocrText} onChange={(e) => setOcrText(e.target.value)} />
        </label>

        <label className={styles.field}>
          <span>Tags (comma-separated)</span>
          <input type="text" value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
        </label>

        <label className={styles.field}>
          <span>Source URL</span>
          <input type="text" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
        </label>

        <div className={styles.actions}>
          <button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
          <button type="button" className={styles.deleteButton} onClick={handleDelete}>
            Delete meme
          </button>
        </div>

        {saveMessage && (
          <p className={saveMessage.kind === "success" ? styles.success : styles.errorMessage}>
            {saveMessage.text}
          </p>
        )}
      </form>

      <dl className={styles.meta}>
        <dt>Original filename</dt>
        <dd>{meme.originalFilename}</dd>
        <dt>Uploaded</dt>
        <dd>{new Date(meme.uploadedAt).toLocaleString()}</dd>
        <dt>File hash</dt>
        <dd className={styles.hash}>{meme.fileHash}</dd>
      </dl>
    </main>
  );
}
