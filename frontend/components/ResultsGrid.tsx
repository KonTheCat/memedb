import type { DisplayMeme } from "@/lib/display";
import MemeCard from "./MemeCard";
import styles from "./ResultsGrid.module.css";

interface Props {
  memes: DisplayMeme[];
  loading: boolean;
  error: string | null;
  onDelete: (id: string) => void;
}

export default function ResultsGrid({ memes, loading, error, onDelete }: Props) {
  if (loading) return <p className={styles.message}>Loading…</p>;
  if (error) return <p className={styles.error}>{error}</p>;
  if (memes.length === 0) return <p className={styles.message}>No memes found.</p>;

  return (
    <div className={styles.grid}>
      {memes.map((meme) => (
        <MemeCard key={meme.id} meme={meme} onDelete={onDelete} />
      ))}
    </div>
  );
}
