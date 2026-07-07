"use client";

import { CATEGORIES } from "@/lib/categories";
import styles from "./CategoryFilter.module.css";

interface Props {
  selected: string | null;
  onSelect: (category: string | null) => void;
}

export default function CategoryFilter({ selected, onSelect }: Props) {
  return (
    <div className={styles.row}>
      <button
        className={selected === null ? styles.active : styles.button}
        onClick={() => onSelect(null)}
      >
        All
      </button>
      {CATEGORIES.map((category) => (
        <button
          key={category}
          className={selected === category ? styles.active : styles.button}
          onClick={() => onSelect(category)}
        >
          {category}
        </button>
      ))}
    </div>
  );
}
