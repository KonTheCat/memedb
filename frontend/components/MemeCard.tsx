"use client";

import Image from "next/image";
import Link from "next/link";
import { AuthenticatedTemplate } from "@azure/msal-react";
import { imageUrl } from "@/lib/api";
import type { DisplayMeme } from "@/lib/display";
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
            {meme.similarity !== undefined && (
              <span className={styles.similarity}>{(meme.similarity * 100).toFixed(0)}%</span>
            )}
          </div>
          <span className={styles.category}>{meme.category}</span>
          {meme.ocrText && <p className={styles.text}>{meme.ocrText}</p>}
          {!meme.ocrText && meme.caption && <p className={styles.text}>{meme.caption}</p>}
          {meme.tags.length > 0 && (
            <div className={styles.tags}>
              {meme.tags.map((tag) => (
                <span key={tag} className={styles.tag}>
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
