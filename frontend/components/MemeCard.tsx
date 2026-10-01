"use client";

import Image from "next/image";
import Link from "next/link";
import { AuthenticatedTemplate } from "@azure/msal-react";
import { imageUrl } from "@/lib/api";
import { bucketLabel, highlightSegments, isTagMatched, type DisplayMeme } from "@/lib/display";
import styles from "./MemeCard.module.css";

interface Props {
  meme: DisplayMeme;
  onDelete: (id: string) => void;
}

export default function MemeCard({ meme, onDelete }: Props) {
  function handleDelete() {
    if (window.confirm("Delete this meme? This cannot be undone.")) {
      onDelete(meme.id);
    }
  }

  const matchedTerms = meme.matchedTerms ?? [];
  const bodyText = meme.ocrText || meme.caption;
  const segments = bodyText ? highlightSegments(bodyText, matchedTerms) : [];

  return (
    <div className={styles.card}>
      <AuthenticatedTemplate>
        <button className={styles.deleteButton} onClick={handleDelete} aria-label="Delete meme" type="button">
          ✕
        </button>
      </AuthenticatedTemplate>
      <Link href={`/meme?id=${meme.id}`} className={styles.link}>
        <div className={styles.imageWrapper}>
          <Image
            src={imageUrl(meme.id)}
            alt={meme.templateName || meme.caption || "meme"}
            fill
            sizes="(max-width: 600px) 50vw, 25vw"
            className={styles.image}
            unoptimized
          />
        </div>
        <div className={styles.body}>
          <div className={styles.headerRow}>
            <span className={styles.template}>{meme.templateName || "Untitled"}</span>
            {meme.bucket && <span className={`${styles.bucket} ${styles[meme.bucket]}`}>{bucketLabel(meme.bucket)}</span>}
          </div>
          <span className={styles.category}>{meme.category}</span>
          {bodyText && (
            <p className={styles.text}>
              {segments.map((segment, i) =>
                segment.highlighted ? (
                  <mark key={i} className={styles.highlight}>
                    {segment.text}
                  </mark>
                ) : (
                  <span key={i}>{segment.text}</span>
                ),
              )}
            </p>
          )}
          {meme.tags.length > 0 && (
            <div className={styles.tags}>
              {meme.tags.map((tag) => (
                <span
                  key={tag}
                  className={isTagMatched(tag, matchedTerms) ? `${styles.tag} ${styles.tagMatched}` : styles.tag}
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </Link>
    </div>
  );
}
