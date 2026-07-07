"use client";

import { useRef, useState } from "react";
import styles from "./SearchBar.module.css";

export type SearchMode = "text" | "image";

interface Props {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  onTextSearch: (query: string) => void;
  onImageSearch: (file: File) => void;
}

export default function SearchBar({ mode, onModeChange, onTextSearch, onImageSearch }: Props) {
  const [query, setQuery] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function submitText(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) onTextSearch(query.trim());
  }

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) onImageSearch(file);
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.toggle}>
        <button
          className={mode === "text" ? styles.activeTab : styles.tab}
          onClick={() => onModeChange("text")}
        >
          Text search
        </button>
        <button
          className={mode === "image" ? styles.activeTab : styles.tab}
          onClick={() => onModeChange("image")}
        >
          Image search
        </button>
      </div>

      {mode === "text" ? (
        <form className={styles.textForm} onSubmit={submitText}>
          <input
            className={styles.input}
            type="text"
            placeholder='Search memes, e.g. "surprised pikachu face"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className={styles.submit} type="submit">
            Search
          </button>
        </form>
      ) : (
        <div
          className={dragging ? styles.dropzoneActive : styles.dropzone}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>Drag &amp; drop an image here, or click to choose one</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      )}
    </div>
  );
}
