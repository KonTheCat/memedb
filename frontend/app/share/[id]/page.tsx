"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Image from "next/image";
import { ApiError, getPublicMeme, type PublicMemeResponse } from "@/lib/api";
import styles from "./page.module.css";

export default function SharePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [meme, setMeme] = useState<PublicMemeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPublicMeme(id)
      .then((doc) => { if (!cancelled) setMeme(doc); })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError && err.status === 404 ? "Meme not found." : "Failed to load meme.");
      });
    return () => { cancelled = true; };
  }, [id]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!meme) return <p className={styles.loading}>Loading…</p>;

  return (
    <main className={styles.main}>
      <div className={styles.imageWrapper}>
        <Image
          src={meme.blobUrl}
          alt={meme.templateName || meme.caption || "meme"}
          fill
          sizes="(max-width: 700px) 100vw, 700px"
          className={styles.image}
          unoptimized
        />
      </div>

      <div className={styles.body}>
        {meme.templateName && <h1 className={styles.title}>{meme.templateName}</h1>}
        {meme.ocrText && <p className={styles.text}>{meme.ocrText}</p>}
        {!meme.ocrText && meme.caption && <p className={styles.text}>{meme.caption}</p>}

        {meme.tags.length > 0 && (
          <div className={styles.tags}>
            {meme.tags.map((tag) => (
              <span key={tag} className={styles.tag}>{tag}</span>
            ))}
          </div>
        )}

        <dl className={styles.meta}>
          <dt>Category</dt>
          <dd>{meme.category}</dd>
          {meme.sourceUrl && (
            <>
              <dt>Source</dt>
              <dd><a href={meme.sourceUrl} target="_blank" rel="noopener noreferrer" className={styles.link}>{meme.sourceUrl}</a></dd>
            </>
          )}
        </dl>
      </div>
    </main>
  );
}
