"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { ApiError, deleteMeme, getMeme, imageUrl, recordView, updateMeme, type MemeResponse } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { loginRequest } from "@/lib/msalConfig";
import LogoutButton from "@/components/LogoutButton";
import styles from "./page.module.css";

function MemeDetail({ id }: { id: string }) {
  const router = useRouter();
  const { instance } = useMsal();

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
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load meme data on mount / id change
    setLoading(true);
    setError(null);
    getMeme(id)
      .then((doc) => {
        if (cancelled) return;
        setMeme(doc);
        recordView(id);
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

  function handleCopyShareLink() {
    navigator.clipboard.writeText(`${window.location.origin}/share?id=${id}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
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
      <AuthenticatedTemplate>
        <LogoutButton />
      </AuthenticatedTemplate>
      <Link href="/" className={styles.back}>
        ← Back
      </Link>

      <div className={styles.imageWrapper}>
        <Image
          src={imageUrl(id)}
          alt={meme.templateName || meme.caption || "meme"}
          fill
          sizes="(max-width: 700px) 100vw, 700px"
          className={styles.image}
          unoptimized
        />
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
          <AuthenticatedTemplate>
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </AuthenticatedTemplate>
          <button type="button" className={styles.shareButton} onClick={handleCopyShareLink}>
            {copied ? "Copied!" : "Copy share link"}
          </button>
          <AuthenticatedTemplate>
            <button type="button" className={styles.deleteButton} onClick={handleDelete}>
              Delete meme
            </button>
          </AuthenticatedTemplate>
          <UnauthenticatedTemplate>
            <button type="button" onClick={() => instance.loginRedirect(loginRequest)}>
              Sign in to edit
            </button>
          </UnauthenticatedTemplate>
        </div>

        {saveMessage && (
          <p className={saveMessage.kind === "success" ? styles.success : styles.errorMessage}>
            {saveMessage.text}
          </p>
        )}
      </form>

      <dl className={styles.meta}>
        <dt>Views</dt>
        <dd>{meme.viewCount}</dd>
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

function MemeDetailPage() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  if (!id) return <p className={styles.error}>No meme id given.</p>;

  return <MemeDetail id={id} />;
}

export default function MemePage() {
  return (
    <Suspense fallback={<p className={styles.message}>Loading…</p>}>
      <MemeDetailPage />
    </Suspense>
  );
}
